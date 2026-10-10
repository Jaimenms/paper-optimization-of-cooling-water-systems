"""Solver layer: SCIP in-process (default, pip-installable) or any Pyomo-registered solver."""

from __future__ import annotations

import logging
import math
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pyomo.environ as pyo

log = logging.getLogger(__name__)


@dataclass
class SolverSettings:
    """Numerical settings. Defaults mirror the GAMS runs (optcr = optca = 1e-3)."""

    name: str = "nlpbb"  # "nlpbb" (NLP branch-and-bound, IPOPT nodes) | "bonmin" | "ipopt" | "scip" | any Pyomo solver name
    executable: str | None = None
    rel_gap: float = 1e-3
    abs_gap: float = 1e-3
    time_limit_s: float = 900.0
    threads: int = 0  # 0 = SCIP default
    verbose: bool = False
    warm_start: bool = True
    options: dict = field(default_factory=dict)
    keep_files: bool = False
    cutoff: float | None = None  # objective value of a known feasible solution (prunes the tree)
    isolate: bool | None = None  # run branch-and-bound in a child process (default: yes for bonmin MINLPs)
    max_node_iter: int = 1000  # IPOPT iteration limit inside the branch-and-bound nodes
    multistart: int = 4  # nlpbb: extra valve starting points when polishing a design
    local_search_steps: int = 1  # nlpbb: neighbourhood radius (catalogue steps) of the final local search; 0 disables


@dataclass
class SolveReport:
    solver: str
    status: str
    termination: str  # optimal | feasible | infeasible | unbounded | limit | error
    objective: float | None
    bound: float | None
    gap: float | None
    time_s: float
    n_solutions: int = 0
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.termination in ("optimal", "feasible")

    def to_dict(self) -> dict:
        return asdict(self)


class SolverError(RuntimeError):
    pass


def available_solvers() -> dict[str, bool]:
    """Which solver back-ends can be used in this environment."""
    out = {}
    try:
        import casadi

        out["nlpbb"] = bool(casadi.has_nlpsol("ipopt"))
        out["bonmin"] = bool(casadi.has_nlpsol("bonmin"))
        out["ipopt"] = bool(casadi.has_nlpsol("ipopt"))
    except ImportError:
        out["nlpbb"] = out["bonmin"] = out["ipopt"] = False
    try:
        import pyscipopt  # noqa: F401

        out["scip"] = True
    except ImportError:
        out["scip"] = False
    for exe in ("bonmin", "couenne", "scip", "ipopt"):
        out[f"{exe}-exe"] = shutil.which(exe) is not None
    return out


def solve_model(model: pyo.ConcreteModel, settings: SolverSettings | None = None) -> SolveReport:
    """Solve a model in place (variable values are loaded back) and return a report."""
    settings = settings or SolverSettings()
    if settings.name == "nlpbb":
        return _solve_with_nlpbb(model, settings)
    if settings.name in ("bonmin", "ipopt"):
        return _solve_with_casadi(model, settings)
    if settings.name == "scip":
        return _solve_with_pyscipopt(model, settings)
    return _solve_with_pyomo_shell(model, settings)


# --------------------------------------------------------------------------- #
# NLP-based branch-and-bound (IPOPT nodes) - the SBB analogue, implemented here
# --------------------------------------------------------------------------- #
FEASIBILITY_TOL = 1e-5


def _solve_with_nlpbb(model: pyo.ConcreteModel, settings: SolverSettings) -> SolveReport:
    from coolingnet.optimization.casadi_bridge import has_free_discrete, max_constraint_violation
    from coolingnet.optimization.nlpbb import NlpBranchAndBound

    t0 = time.perf_counter()
    target = pyo.TransformationFactory("core.scale_model").create_using(model) if hasattr(model, "scaling_factor") else model
    sf = model.scaling_factor[model.obj] if hasattr(model, "scaling_factor") and model.obj in model.scaling_factor else 1.0
    bb = NlpBranchAndBound(
        target,
        rel_gap=settings.rel_gap,
        abs_gap=settings.abs_gap * sf,
        time_limit_s=settings.time_limit_s,
        max_node_iter=settings.max_node_iter,
        verbose=settings.verbose,
        cutoff=None if settings.cutoff is None else settings.cutoff * sf,
        ipopt_options=settings.options,
        multistart=settings.multistart,
        local_search_steps=settings.local_search_steps,
    )
    res = bb.run() if has_free_discrete(model) else bb.solve_fixed()
    if res.x is not None:
        bb.load(res.x)
        if target is not model:
            pyo.TransformationFactory("core.scale_model").propagate_solution(target, model)
            for v in model.component_data_objects(pyo.Var, active=True, descend_into=True):
                if (v.is_integer() or v.is_binary()) and not v.fixed and v.value is not None:
                    v.set_value(float(round(v.value)), skip_validation=True)
    viol = max_constraint_violation(model) if res.x is not None else math.inf
    feasible = viol <= FEASIBILITY_TOL
    termination = res.status if feasible else ("infeasible" if res.status == "infeasible" else "error")
    if settings.cutoff is not None and res.x is None and res.status == "infeasible":
        termination = "cutoff"
    return SolveReport(
        solver="nlpbb (ipopt nodes)",
        status=res.status,
        termination=termination,
        objective=pyo.value(model.fob) if feasible else None,
        bound=None if res.bound is None else res.bound / sf,
        gap=None,
        time_s=time.perf_counter() - t0,
        n_solutions=int(feasible),
        message=f"{res.message}; nodes={res.nodes} nlps={res.nlps}; max constraint violation {viol:.2e}",
    )



def _solve_with_casadi(model: pyo.ConcreteModel, settings: SolverSettings) -> SolveReport:
    from coolingnet.optimization.casadi_bridge import CasadiSolveError, max_constraint_violation, solve_with_casadi

    options = dict(settings.options)
    if settings.name == "bonmin":
        options.setdefault("max_iter", settings.max_node_iter)
    if settings.cutoff is not None and settings.name == "bonmin":
        sf = model.scaling_factor[model.obj] if hasattr(model, "scaling_factor") and model.obj in model.scaling_factor else 1.0
        options.setdefault("cutoff", settings.cutoff * sf)
    t0 = time.perf_counter()
    try:
        res = solve_with_casadi(
            model,
            settings.name,
            rel_gap=settings.rel_gap,
            abs_gap=settings.abs_gap,
            time_limit_s=settings.time_limit_s,
            verbose=settings.verbose,
            options=options,
        )
    except CasadiSolveError as exc:
        log.warning("%s failed: %s", settings.name, exc)
        return SolveReport(
            solver=f"{settings.name} (casadi)",
            status="exception",
            termination="error",
            objective=None,
            bound=None,
            gap=None,
            time_s=time.perf_counter() - t0,
            n_solutions=0,
            message=str(exc)[:500],
        )
    viol = max_constraint_violation(model)
    feasible = viol <= FEASIBILITY_TOL
    status = res.status
    if feasible and res.success:
        termination = "optimal"
    elif feasible:
        termination = "feasible"
    elif "INFEASIBLE" in status.upper():
        termination = "infeasible"
    else:
        termination = "error"
    objective = pyo.value(model.fob) if feasible else None
    note = f"max constraint violation {viol:.2e}"
    if res.stats.get("retried"):
        note += "; solved with the fallback Bonmin configuration"
    if settings.cutoff is not None and not feasible and "INFEASIBLE" in status.upper():
        note += f"; no solution better than the cutoff {settings.cutoff:.1f}"
        termination = "cutoff"
    return SolveReport(
        solver=f"{settings.name} (casadi)",
        status=status,
        termination=termination,
        objective=objective,
        bound=None,
        gap=None,
        time_s=res.time_s,
        n_solutions=int(feasible),
        message=note,
    )


# --------------------------------------------------------------------------- #
# SCIP in-process through the AMPL .nl interface
# --------------------------------------------------------------------------- #
_SCIP_STATUS = {
    "optimal": "optimal",
    "gaplimit": "feasible",
    "timelimit": "feasible",
    "nodelimit": "feasible",
    "sollimit": "feasible",
    "bestsollimit": "feasible",
    "userinterrupt": "feasible",
    "infeasible": "infeasible",
    "unbounded": "unbounded",
    "inforunbd": "infeasible",
}


def _solve_with_pyscipopt(model: pyo.ConcreteModel, settings: SolverSettings) -> SolveReport:
    try:
        import pyscipopt as scip
    except ImportError as exc:  # pragma: no cover
        raise SolverError("pyscipopt is not installed (pip install pyscipopt)") from exc

    t0 = time.perf_counter()
    workdir = Path(tempfile.mkdtemp(prefix="coolingnet_scip_"))
    try:
        nl_path = workdir / "model.nl"
        model.write(str(nl_path), format="nl", io_options={"symbolic_solver_labels": True, "linear_presolve": False})
        s = scip.Model()
        if not settings.verbose:
            s.hideOutput()
        s.readProblem(str(nl_path))
        s.setParam("limits/gap", settings.rel_gap)
        s.setParam("limits/absgap", settings.abs_gap)
        s.setParam("limits/time", settings.time_limit_s)
        if settings.threads:
            s.setParam("parallel/maxnthreads", settings.threads)
        for key, val in settings.options.items():
            s.setParam(key, val)

        pyomo_vars = {v.name: v for v in model.component_data_objects(pyo.Var, active=True, descend_into=True) if not v.fixed}
        scip_vars = {v.name: v for v in s.getVars()}
        missing = set(scip_vars) - set(pyomo_vars)
        if missing:
            raise SolverError(f"variables in the .nl file not found in the Pyomo model: {sorted(missing)[:5]}")

        if settings.warm_start:
            _add_warm_start(s, scip_vars, pyomo_vars)

        s.optimize()
        status = s.getStatus()
        n_sols = s.getNSols()
        objective = bound = gap = None
        if n_sols > 0:
            best = s.getBestSol()
            for name, sv in scip_vars.items():
                pyomo_vars[name].set_value(s.getSolVal(best, sv), skip_validation=True)
            objective = s.getObjVal()
            bound = s.getDualbound()
            gap = s.getGap()
        termination = _SCIP_STATUS.get(status, "error")
        if n_sols == 0 and termination == "feasible":
            termination = "limit"
        return SolveReport(
            solver=f"scip {s.version()}",
            status=status,
            termination=termination,
            objective=objective,
            bound=bound,
            gap=gap,
            time_s=time.perf_counter() - t0,
            n_solutions=n_sols,
        )
    finally:
        if settings.keep_files:
            log.info("solver files kept in %s", workdir)
        else:
            shutil.rmtree(workdir, ignore_errors=True)


def _add_warm_start(s, scip_vars: dict, pyomo_vars: dict) -> None:
    """Pass the current Pyomo values to SCIP as a (possibly partial) starting solution."""
    values = {}
    for name, pv in pyomo_vars.items():
        if name in scip_vars and pv.value is not None:
            values[name] = float(pv.value)
    if not values:
        return
    try:
        sol = s.createSol()
        for name, val in values.items():
            s.setSolVal(sol, scip_vars[name], val)
        accepted = s.addSol(sol, free=True)
        if accepted:
            return
    except Exception as exc:  # pragma: no cover - defensive
        log.debug("full warm start rejected: %s", exc)
    try:
        sol = s.createPartialSol()
        for name, val in values.items():
            if scip_vars[name].vtype() in ("BINARY", "INTEGER"):
                s.setSolVal(sol, scip_vars[name], round(val))
        s.addSol(sol, free=True)
    except Exception as exc:  # pragma: no cover - defensive
        log.debug("partial warm start rejected: %s", exc)


# --------------------------------------------------------------------------- #
# Any other solver registered in Pyomo (bonmin, couenne, ipopt, scip executable, ...)
# --------------------------------------------------------------------------- #
_OPTION_MAPS = {
    "bonmin": lambda st: {"bonmin.allowable_fraction_gap": st.rel_gap, "bonmin.allowable_gap": st.abs_gap, "bonmin.time_limit": st.time_limit_s},
    "couenne": lambda st: {},
    "scip-exe": lambda st: {"limits/gap": st.rel_gap, "limits/absgap": st.abs_gap, "limits/time": st.time_limit_s},
    "ipopt": lambda st: {"max_cpu_time": st.time_limit_s},
}


def _solve_with_pyomo_shell(model: pyo.ConcreteModel, settings: SolverSettings) -> SolveReport:
    name = "scip" if settings.name == "scip-exe" else settings.name
    opt = pyo.SolverFactory(name, executable=settings.executable) if settings.executable else pyo.SolverFactory(name)
    if opt is None or not opt.available(exception_flag=False):
        raise SolverError(f"solver {settings.name!r} is not available (executable={settings.executable})")
    for key, val in {**_OPTION_MAPS.get(settings.name, lambda st: {})(settings), **settings.options}.items():
        opt.options[key] = val
    t0 = time.perf_counter()
    results = opt.solve(model, tee=settings.verbose, load_solutions=False, warmstart=settings.warm_start) if name in ("bonmin",) else opt.solve(model, tee=settings.verbose, load_solutions=False)
    tc = str(results.solver.termination_condition)
    status = str(results.solver.status)
    has_solution = len(results.solution) > 0
    if has_solution:
        model.solutions.load_from(results)
    if tc in ("optimal", "locallyOptimal", "globallyOptimal"):
        termination = "optimal"
    elif tc in ("feasible", "maxTimeLimit", "maxIterations", "maxEvaluations", "other") and has_solution:
        termination = "feasible"
    elif tc in ("infeasible", "infeasibleOrUnbounded"):
        termination = "infeasible"
    elif tc == "unbounded":
        termination = "unbounded"
    else:
        termination = "limit" if not has_solution else "feasible"
    objective = pyo.value(model.fob) if has_solution else None
    bound = None
    try:
        bound = float(results.problem.lower_bound)
    except Exception:
        pass
    gap = None
    if objective is not None and bound is not None and abs(objective) > 1e-12:
        gap = abs(objective - bound) / abs(objective)
    return SolveReport(
        solver=settings.name,
        status=status,
        termination=termination,
        objective=objective,
        bound=bound,
        gap=gap,
        time_s=time.perf_counter() - t0,
        n_solutions=int(has_solution),
        message=tc,
    )
