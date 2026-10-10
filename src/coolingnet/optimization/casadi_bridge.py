"""Translate a Pyomo model into a CasADi NLP/MINLP and solve it with Bonmin or IPOPT.

CasADi wheels bundle IPOPT (local NLP) and Bonmin (NLP-based branch-and-bound),
which is the pip-installable analogue of the SBB + CONOPT pair used in the paper.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import pyomo.environ as pyo
from pyomo.core.expr import numeric_expr as nx
from pyomo.core.expr.visitor import StreamBasedExpressionVisitor

try:
    import casadi as ca
except ImportError:  # pragma: no cover
    ca = None


class CasadiTranslationError(RuntimeError):
    pass


_UNARY = {
    "exp": lambda x: ca.exp(x),
    "log": lambda x: ca.log(x),
    "log10": lambda x: ca.log10(x),
    "sqrt": lambda x: ca.sqrt(x),
    "sin": lambda x: ca.sin(x),
    "cos": lambda x: ca.cos(x),
    "tan": lambda x: ca.tan(x),
    "abs": lambda x: ca.fabs(x),
}


class _ToCasadi(StreamBasedExpressionVisitor):
    def __init__(self, symbols: dict[int, object]):
        super().__init__()
        self.symbols = symbols

    def _leaf(self, child):
        """Translate a leaf (number, variable, parameter); returns (is_leaf, value)."""
        if child.__class__ in nx.native_numeric_types:
            return True, float(child)
        if not child.is_expression_type():
            if child.is_variable_type():
                if child.fixed:
                    return True, float(child.value)
                try:
                    return True, self.symbols[id(child)]
                except KeyError as exc:
                    raise CasadiTranslationError(f"variable {child.name} has no symbol") from exc
            return True, float(pyo.value(child))  # parameters / constants
        return False, None

    def initializeWalker(self, expr):  # noqa: N802 (Pyomo API)
        is_leaf, val = self._leaf(expr)
        if is_leaf:
            return False, val
        return True, expr

    def beforeChild(self, node, child, child_idx):  # noqa: N802 (Pyomo API)
        is_leaf, val = self._leaf(child)
        if is_leaf:
            return False, val
        return True, None

    def exitNode(self, node, data):  # noqa: N802 (Pyomo API)
        if isinstance(node, nx.SumExpression):  # includes LinearExpression
            total = 0
            for d in data:
                total = total + d
            return total
        if isinstance(node, (nx.ProductExpression, nx.MonomialTermExpression)):
            return data[0] * data[1]
        if isinstance(node, nx.DivisionExpression):
            return data[0] / data[1]
        if isinstance(node, nx.PowExpression):
            base, expo = data[0], data[1]
            if isinstance(expo, float) and not float(expo).is_integer():
                # Fractional powers are NaN for negative bases. Variables with such powers
                # are bounded below by 0 in the model; the guard only affects iterates that
                # a line search / branching step would otherwise push outside the bounds.
                return ca.fabs(base) ** expo
            return base**expo
        if isinstance(node, nx.NegationExpression):
            return -data[0]
        if isinstance(node, nx.AbsExpression):
            return ca.fabs(data[0])
        if isinstance(node, nx.UnaryFunctionExpression):
            try:
                return _UNARY[node.getname()](data[0])
            except KeyError as exc:
                raise CasadiTranslationError(f"unsupported function {node.getname()}") from exc
        if isinstance(node, nx.Expr_ifExpression):
            return ca.if_else(data[0], data[1], data[2])
        if node.is_named_expression_type():
            return data[0]
        if hasattr(node, "nargs") and node.nargs() == 1:
            return data[0]
        raise CasadiTranslationError(f"unsupported expression node {type(node).__name__}")


@dataclass
class CasadiProblem:
    variables: list  # Pyomo VarData in x order
    x: object
    f: object
    g: object
    lbx: list[float]
    ubx: list[float]
    x0: list[float]
    lbg: list[float]
    ubg: list[float]
    discrete: list[bool]
    constraints: list  # Pyomo ConstraintData in g order


def translate(model: pyo.ConcreteModel) -> CasadiProblem:
    if ca is None:  # pragma: no cover
        raise CasadiTranslationError("casadi is not installed (pip install casadi)")
    variables = [v for v in model.component_data_objects(pyo.Var, active=True, descend_into=True) if not v.fixed]
    syms = [ca.SX.sym(f"x{i}") for i, _ in enumerate(variables)]
    symbols = {id(v): s for v, s in zip(variables, syms, strict=True)}
    visitor = _ToCasadi(symbols)

    lbx, ubx, x0, discrete = [], [], [], []
    for v in variables:
        lb = -math.inf if v.lb is None else float(v.lb)
        ub = math.inf if v.ub is None else float(v.ub)
        is_int = v.is_integer() or v.is_binary()
        lbx.append(lb)
        ubx.append(ub)
        discrete.append(bool(is_int))
        val = v.value
        if val is None or not math.isfinite(val):
            val = 0.0 if (lb <= 0.0 <= ub) else (lb if math.isfinite(lb) else ub)
        x0.append(min(max(float(val), lb), ub))

    g_list, lbg, ubg, cons = [], [], [], []
    for c in model.component_data_objects(pyo.Constraint, active=True, descend_into=True):
        body = visitor.walk_expression(c.body)
        lb = -math.inf if c.lb is None else float(c.lb)
        ub = math.inf if c.ub is None else float(c.ub)
        g_list.append(body)
        lbg.append(lb)
        ubg.append(ub)
        cons.append(c)
    objs = list(model.component_data_objects(pyo.Objective, active=True, descend_into=True))
    if len(objs) != 1:
        raise CasadiTranslationError(f"expected one active objective, found {len(objs)}")
    f = visitor.walk_expression(objs[0].expr)
    if objs[0].sense == pyo.maximize:
        f = -f
    return CasadiProblem(
        variables=variables,
        x=ca.vertcat(*syms) if syms else ca.SX.sym("empty", 0),
        f=f,
        g=ca.vertcat(*g_list) if g_list else ca.SX.sym("emptyg", 0),
        lbx=lbx,
        ubx=ubx,
        x0=x0,
        lbg=lbg,
        ubg=ubg,
        discrete=discrete,
        constraints=cons,
    )


@dataclass
class CasadiResult:
    status: str
    success: bool
    objective: float | None
    time_s: float
    stats: dict


IPOPT_DEFAULTS = {
    "sb": "yes",
    "bound_relax_factor": 0.0,  # x**0.8, x**1.852 are NaN for x < 0: keep iterates inside the bounds
    "honor_original_bounds": "yes",
    "mu_strategy": "adaptive",
    "max_iter": 5000,
    "tol": 1e-8,
    "nlp_scaling_method": "gradient-based",
    "check_derivatives_for_naninf": "yes",
}

# Conservative Bonmin settings used when the default branch-and-bound raises an internal error
BONMIN_FALLBACK = {
    "variable_selection": "most-fractional",
    "num_resolve_at_root": 0,
    "num_resolve_at_infeasibles": 0,
    "num_resolve_at_node": 0,
    "max_iter": 3000,
}


class CasadiSolveError(RuntimeError):
    pass


def has_free_discrete(model: pyo.ConcreteModel) -> bool:
    return any((v.is_integer() or v.is_binary()) and not v.fixed for v in model.component_data_objects(pyo.Var, active=True, descend_into=True))


def solve_with_casadi(
    model: pyo.ConcreteModel,
    solver: str = "bonmin",
    *,
    rel_gap: float = 1e-3,
    abs_gap: float = 1e-3,
    time_limit_s: float = 900.0,
    verbose: bool = False,
    relax_integrality: bool = False,
    options: dict | None = None,
    scale: bool = True,
) -> CasadiResult:
    """Solve `model` in place with CasADi's Bonmin (MINLP) or IPOPT (NLP).

    With `scale=True` the model is scaled with the `scaling_factor` suffix
    (Pyomo `core.scale_model`) before translation and the solution is propagated back.
    """
    if solver == "bonmin" and not has_free_discrete(model):
        solver = "ipopt"  # no branching needed
    target = model
    if scale and hasattr(model, "scaling_factor"):
        target = pyo.TransformationFactory("core.scale_model").create_using(model)
    try:
        res = _solve_casadi_core(target, solver, rel_gap=rel_gap, abs_gap=abs_gap, time_limit_s=time_limit_s, verbose=verbose, relax_integrality=relax_integrality, options=options)
    except RuntimeError as first_error:
        if solver != "bonmin":
            raise CasadiSolveError(str(first_error)) from first_error
        # Bonmin occasionally dies inside a strong-branching NLP ("Uncaught error in Bonmin");
        # retry once with a conservative configuration before giving up.
        retry = {**BONMIN_FALLBACK, **(options or {})}
        try:
            res = _solve_casadi_core(target, solver, rel_gap=rel_gap, abs_gap=abs_gap, time_limit_s=time_limit_s, verbose=verbose, relax_integrality=relax_integrality, options=retry)
            res.stats["retried"] = True
        except RuntimeError as second_error:
            raise CasadiSolveError(f"bonmin failed twice: {first_error} / {second_error}") from second_error
    if target is not model:
        pyo.TransformationFactory("core.scale_model").propagate_solution(target, model)
        for v in model.component_data_objects(pyo.Var, active=True, descend_into=True):
            if (v.is_integer() or v.is_binary()) and not v.fixed and v.value is not None and not relax_integrality:
                v.set_value(float(round(v.value)), skip_validation=True)
    return res


def _solve_casadi_core(
    model: pyo.ConcreteModel,
    solver: str,
    *,
    rel_gap: float,
    abs_gap: float,
    time_limit_s: float,
    verbose: bool,
    relax_integrality: bool,
    options: dict | None,
) -> CasadiResult:
    prob = translate(model)
    t0 = time.perf_counter()
    opts: dict = {"print_time": False, "error_on_fail": False}
    if solver == "bonmin":
        bon = {
            **IPOPT_DEFAULTS,
            "algorithm": "B-BB",
            "allowable_fraction_gap": rel_gap,
            "allowable_gap": abs_gap,
            "time_limit": time_limit_s,
            "bb_log_level": 1 if verbose else 0,
            "nlp_log_level": 0,
            "print_level": 5 if verbose else 0,
            "num_resolve_at_root": 2,
            "num_resolve_at_infeasibles": 1,
            "nlp_failure_behavior": "fathom",
            "node_comparison": "best-bound",
            "random_generator_seed": 0,
        }
        bon.update(options or {})
        opts["bonmin"] = bon
        opts["discrete"] = [False] * len(prob.discrete) if relax_integrality else prob.discrete
        plugin = "bonmin"
    elif solver == "ipopt":
        ipo = {**IPOPT_DEFAULTS, "print_level": 5 if verbose else 0, "max_cpu_time": time_limit_s}
        ipo.update(options or {})
        opts["ipopt"] = ipo
        plugin = "ipopt"
        if any(prob.discrete) and not relax_integrality:
            # IPOPT cannot branch: integer variables keep their (rounded) current value
            for v, d in zip(prob.variables, prob.discrete, strict=True):
                if d:
                    v.fix(round(v.value or 0))
            prob = translate(model)
    else:
        raise ValueError(f"unknown casadi solver {solver!r}")

    nlp = {"x": prob.x, "f": prob.f, "g": prob.g}
    S = ca.nlpsol("S", plugin, nlp, opts)
    res = S(x0=prob.x0, lbx=prob.lbx, ubx=prob.ubx, lbg=prob.lbg, ubg=prob.ubg)
    stats = S.stats()
    x = res["x"].full().ravel()
    for v, val, d in zip(prob.variables, x, prob.discrete, strict=True):
        v.set_value(float(round(val)) if (d and not relax_integrality) else float(val), skip_validation=True)
    status = str(stats.get("return_status", "unknown"))
    return CasadiResult(
        status=status,
        success=bool(stats.get("success", status.upper().startswith("SUCCESS") or status == "Solve_Succeeded")),
        objective=float(res["f"]),
        time_s=time.perf_counter() - t0,
        stats={k: v for k, v in stats.items() if isinstance(v, (int, float, str, bool))},
    )


def max_constraint_violation(model: pyo.ConcreteModel) -> float:
    """Largest absolute violation of the active constraints at the current point."""
    worst = 0.0
    for c in model.component_data_objects(pyo.Constraint, active=True, descend_into=True):
        body = pyo.value(c.body, exception=False)
        if body is None:
            return math.inf
        if c.lb is not None:
            worst = max(worst, float(c.lb) - body)
        if c.ub is not None:
            worst = max(worst, body - float(c.ub))
    return worst
