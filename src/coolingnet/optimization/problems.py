"""High-level entry points for the problems solved in the paper (Section 3)."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import replace

import pyomo.environ as pyo

from coolingnet.config.schema import CaseStudy
from coolingnet.network.graph import Network, build_network
from coolingnet.optimization.model import build_model, initialize_from_simulation
from coolingnet.optimization.results import Solution
from coolingnet.optimization.solvers import SolveReport, SolverSettings, solve_model
from coolingnet.optimization.spec import Design, ProblemSpec
from coolingnet.simulation.fixed_design import simulate_design

log = logging.getLogger(__name__)


def _run(
    case: CaseStudy,
    spec: ProblemSpec,
    settings: SolverSettings | None,
    network: Network | None,
    warm_start: Solution | None = None,
) -> Solution:
    """Build, initialize and solve one problem; robust to solver failures when a warm start exists."""
    net = network or build_network(case.network)
    settings = settings or SolverSettings()
    m = build_model(case, spec, net)
    # interior starting point: exact state of the existing design (NumPy simulator)
    sim = simulate_design(
        case,
        Design.from_case(case),
        hot_flow_factor=spec.hot_flow_factor,
        tower_model=spec.tower_model,
        network=net,
        penalty_factor=spec.penalty_factor,
    )
    initialize_from_simulation(m, sim)
    incumbent = None
    if warm_start is not None:
        load_warm_start(m, warm_start)
        incumbent = evaluate_design_under_spec(case, spec, warm_start, net)
        if (
            incumbent is not None
            and settings.name == "bonmin"
            and settings.cutoff is None
            and spec.objective == "total_cost"
        ):
            settings = replace(settings, cutoff=incumbent[1] * (1.0 + 1e-4) + 1.0)
    if (
        incumbent is None
        and spec.hydraulics
        and spec.objective == "total_cost"
        and spec.design_free
    ):
        # the existing design with open valves is always feasible for a cost minimization
        existing = spec.existing_design or Design.from_case(case)
        if sim.converged:
            incumbent = (existing, capital_cost(case, existing, existing) + sim.total_cost_USD_y)
    isolate = (
        settings.isolate
        if settings.isolate is not None
        else (settings.name == "bonmin" and spec.design_free and spec.hydraulics)
    )
    if isolate:
        from coolingnet.optimization.casadi_bridge import BONMIN_FALLBACK
        from coolingnet.optimization.isolation import solve_in_subprocess

        child = solve_in_subprocess(case, spec, settings, warm_start)
        if child is None:
            log.warning(
                "%s: retrying in a new process with the conservative Bonmin settings", spec.label
            )
            child = solve_in_subprocess(
                case,
                spec,
                replace(settings, options={**BONMIN_FALLBACK, **settings.options}),
                warm_start,
            )
        if child is not None and (child.ok or incumbent is None):
            log.info(
                "%s: %s obj=%s t=%.1fs",
                spec.label,
                child.report["termination"],
                child.costs.get("fob"),
                child.report["time_s"],
            )
            return child
        report = SolveReport(
            solver=f"{settings.name} (casadi, subprocess)",
            status="crashed" if child is None else child.report["status"],
            termination="error",
            objective=None,
            bound=None,
            gap=None,
            time_s=0.0,
            message="solver process crashed" if child is None else child.report.get("message", ""),
        )
    else:
        report = solve_model(m, settings)
    if not report.ok and incumbent is not None:
        # the warm-start design is feasible: keep it and re-optimize only the valves (NLP)
        log.warning(
            "%s: solver returned %s (%s); falling back to the warm-start design",
            spec.label,
            report.termination,
            report.message,
        )
        fallback_spec = spec.with_(
            design_free=False, existing_design=spec.existing_design or Design.from_case(case)
        )
        m = build_model(case, fallback_spec, net)
        _fix_design(m, incumbent[0])
        initialize_from_simulation(
            m,
            simulate_design(
                case,
                incumbent[0],
                hot_flow_factor=spec.hot_flow_factor,
                tower_model=spec.tower_model,
                network=net,
                penalty_factor=spec.penalty_factor,
            ),
        )
        fb_report = solve_model(m, replace(settings, name="ipopt", cutoff=None))
        fb_report.message = f"fallback to warm-start design after '{report.termination}': {report.message}; {fb_report.message}"
        fb_report.termination = "feasible" if fb_report.ok else fb_report.termination
        report = fb_report
    sol = Solution.from_model(m, report, spec.label)
    log.info(
        "%s: %s obj=%s gap=%s t=%.1fs",
        spec.label,
        report.termination,
        report.objective,
        report.gap,
        report.time_s,
    )
    return sol


def _fix_design(m: pyo.ConcreteModel, design: Design) -> None:
    dnom = m.params["dnom"]
    for p in m.network.pipes:
        for n in m.N:
            m.y_pi[p.id, n].fix(
                1.0 if abs(dnom[n] - design.pipe_diameters_in[p.id]) < 1e-9 else 0.0
            )
    for u in m.network.pumps:
        for s_ in m.S:
            m.y_pu[u.id, s_].fix(1.0 if s_ == design.pump_options[u.id] else 0.0)


def evaluate_design_under_spec(
    case: CaseStudy, spec: ProblemSpec, previous: Solution, network: Network | None = None
) -> tuple[Design, float] | None:
    """Total cost of a previous solution's design + valves under `spec`, or None if infeasible.

    Used to derive a valid cutoff for the branch-and-bound and as a safety net.
    """
    if not spec.hydraulics or spec.objective != "total_cost":
        return None
    net = network or build_network(case.network)
    try:
        design = Design(
            pipe_diameters_in={
                p.id: previous.design["pipe_diameters_in"][str(p.id)] for p in net.pipes
            },
            pump_options={u.id: previous.design["pump_options"][str(u.id)] for u in net.pumps},
        )
    except KeyError:
        return None
    valves = {c["circuit"]: max(0.0, c["valve_head_loss_m"]) for c in previous.circuits}
    sim = simulate_design(
        case,
        design,
        valve_head_losses_m=valves,
        hot_flow_factor=spec.hot_flow_factor,
        tower_model=spec.tower_model,
        network=net,
        penalty_factor=spec.penalty_factor,
    )
    if not sim.converged:
        return None
    pipes = case.pipes
    for v in sim.details["velocities_m_s"].values():
        if v > pipes.v_max_m_s * (1 + 1e-6) or v < pipes.v_min_m_s * (1 - 1e-6):
            return None
    if sim.T_w_feed_C > case.cooling_tower.max_feed_temperature_C * (1 + 1e-6):
        return None
    capital = capital_cost(case, design, spec.existing_design or Design.from_case(case))
    if spec.budget is not None and capital > spec.budget * (1 + 1e-6) + 1e-6:
        return None
    return design, capital + sim.total_cost_USD_y


def capital_cost(case: CaseStudy, design: Design, existing: Design) -> float:
    """Annualized capital cost of the substitutions (pipes and pumps) of `design` vs `existing`."""
    from coolingnet.economics.costs import annualization_factor, pipe_unit_cost, pump_capital_cost

    pipes, pumps, econ = case.pipes, case.pumps, case.economics
    r = annualization_factor(econ.interest_rate, econ.project_years)
    total = 0.0
    for p in case.network.pipes:
        d = design.pipe_diameters_in[p.id]
        if abs(d - existing.pipe_diameters_in[p.id]) > 1e-9:
            total += pipe_unit_cost(d, pipes.cost_c1, pipes.cost_m) * p.length_m
    for u in case.network.pumps:
        opt = design.pump_options[u.id]
        if opt != existing.pump_options[u.id]:
            total += pump_capital_cost(
                pumps.options[opt].coefficients,
                pumps.design_flow_m3_s,
                pumps.cost_FI,
                pumps.cost_Fms,
                pumps.cost_Fm,
                pumps.cost_b,
                r,
            ).annualized_cost_usd_y
    return total


def load_warm_start(m: pyo.ConcreteModel, previous: Solution) -> None:
    """Initialize a model from a previous solution of the same network (binaries and flows)."""
    net = m.network
    if m.spec.hydraulics and "pipe_diameters_in" in previous.design:
        dnom = m.params["dnom"]
        for p in net.pipes:
            d = previous.design["pipe_diameters_in"].get(str(p.id))
            if d is None:
                continue
            for n in m.N:
                if not m.y_pi[p.id, n].fixed:
                    m.y_pi[p.id, n].set_value(1.0 if abs(dnom[n] - d) < 1e-9 else 0.0)
        for u in net.pumps:
            opt = previous.design["pump_options"].get(str(u.id))
            for s in m.S:
                if opt is not None and not m.y_pu[u.id, s].fixed:
                    m.y_pu[u.id, s].set_value(1.0 if s == opt else 0.0)
        for c in previous.circuits:
            if not m.lvalve[c["circuit"]].fixed:
                m.lvalve[c["circuit"]].set_value(c["valve_head_loss_m"])
    by_id = {str(e["id"]): e for e in previous.edges}
    for e in net.edges:
        row = by_id.get(str(e.id))
        if row is not None:
            m.q[e.id].set_value(min(max(row["q_m3_s"], m.q[e.id].lb), m.q[e.id].ub))
    for x in previous.exchangers:
        h = x["edge_id"]
        if h in m.HE:
            m.T_hot_out[h].set_value(x["T_hot_out_C"])
            m.T_w_out[h].set_value(x["T_w_out_C"])
            m.P[h].set_value(x["effectiveness"])
            m.cr[h].set_value(x["CR"])
            m.U[h].set_value(x["U_W_m2K"])
            m.h_w[h].set_value(x["h_w_W_m2K"])
            if hasattr(m, "y_he"):
                m.y_he[h].set_value(1.0 if x["penalty_active"] else 0.0)
            m.che[h].set_value(max(0.0, x["penalty_USD_y"]))
    if not m.T_w_in.fixed:
        m.T_w_in.set_value(previous.tower["T_w_in_C"])
    m.T_w_feed.set_value(previous.tower["T_w_feed_C"])


# --------------------------------------------------------------------------- #
# Section 3.2 - water shortage (simulation of the existing design)
# --------------------------------------------------------------------------- #
def simulate_existing_network(
    case: CaseStudy,
    hot_flow_factor: float = 1.0,
    *,
    settings: SolverSettings | None = None,
    network: Network | None = None,
    label: str | None = None,
) -> Solution:
    """Existing pipes/pump, fully open valves: 'initial' (factor 1.0) or 'current' (factor 1.2) condition."""
    spec = ProblemSpec(
        hot_flow_factor=hot_flow_factor,
        design_free=False,
        valves_free=False,
        label=label or f"simulation_x{hot_flow_factor:g}",
    )
    return _run(case, spec, settings, network)


# --------------------------------------------------------------------------- #
# Sections 3.3 - 3.5 - debottlenecking optimization
# --------------------------------------------------------------------------- #
def optimize_debottlenecking(
    case: CaseStudy,
    *,
    budget: float | None = None,
    penalty_factor: float | dict[str, float] | None = None,
    hot_flow_factor: float | None = None,
    design_free: bool = True,
    settings: SolverSettings | None = None,
    network: Network | None = None,
    warm_start: Solution | None = None,
    label: str | None = None,
    **spec_overrides,
) -> Solution:
    """Minimize Eq. (55): capital (pipes, pump) + operating + penalty costs.

    budget=None  -> Section 3.4 (unlimited budget);
    budget=0.0   -> Section 3.3 (no available budget: only valves move);
    budget=B>0   -> Section 3.5 (finite budget).
    """
    factor = case.scenarios.hot_flow_increase_factor if hot_flow_factor is None else hot_flow_factor
    if label is None:
        if budget is None:
            label = "unlimited_budget"
        elif budget == 0:
            label = "no_budget"
        else:
            label = f"budget_{budget:g}"
    spec = ProblemSpec(
        hot_flow_factor=factor,
        penalty_factor=penalty_factor,
        budget=budget,
        design_free=design_free and budget != 0,
        valves_free=True,
        label=label,
        **spec_overrides,
    )
    return _run(case, spec, settings, network, warm_start)


def budget_sweep(
    case: CaseStudy,
    budgets: Sequence[float],
    *,
    penalty_factor: float | dict[str, float] | None = None,
    settings: SolverSettings | None = None,
    network: Network | None = None,
    warm_start: Solution | None = None,
    on_result=None,
    **spec_overrides,
) -> list[Solution]:
    """Solve the finite-budget problem for every budget value (Figs. 7-8, Video 1)."""
    net = network or build_network(case.network)
    out: list[Solution] = []
    previous = warm_start
    for b in budgets:
        sol = optimize_debottlenecking(
            case,
            budget=float(b),
            penalty_factor=penalty_factor,
            settings=settings,
            network=net,
            warm_start=previous,
            label=f"budget_{b:g}",
            **spec_overrides,
        )
        out.append(sol)
        if sol.ok:
            previous = sol
        if on_result:
            on_result(sol)
    return out


def penalty_sweep(
    case: CaseStudy,
    penalty_factors: Sequence[float],
    *,
    budget: float | None = None,
    settings: SolverSettings | None = None,
    network: Network | None = None,
    warm_start: Solution | None = None,
    on_result=None,
    **spec_overrides,
) -> list[Solution]:
    """Solve the unlimited-budget problem for every penalty factor (Fig. 4)."""
    net = network or build_network(case.network)
    out: list[Solution] = []
    previous = warm_start
    for pen in penalty_factors:
        sol = optimize_debottlenecking(
            case,
            budget=budget,
            penalty_factor=float(pen),
            settings=settings,
            network=net,
            warm_start=previous,
            label=f"penalty_{pen:g}",
            **spec_overrides,
        )
        out.append(sol)
        if sol.ok:
            previous = sol
        if on_result:
            on_result(sol)
    return out


# --------------------------------------------------------------------------- #
# Section 3.7 - purely hydraulic approach (Lee et al., 1997)
# --------------------------------------------------------------------------- #
def desired_water_flow_rates(
    case: CaseStudy,
    hot_flow_factor: float | None = None,
    water_inlet_C: float | None = None,
    *,
    settings: SolverSettings | None = None,
    network: Network | None = None,
) -> Solution:
    """Water flow rate of each cooler that meets its set-point with the current hot flow rates.

    Thermal equations only, with the water supply temperature fixed (Table 12,
    'desired cooling water flow rate').
    """
    factor = case.scenarios.hot_flow_increase_factor if hot_flow_factor is None else hot_flow_factor
    spec = ProblemSpec(
        hot_flow_factor=factor,
        hydraulics=False,
        tower_model="fixed_inlet",
        fix_hot_outlet_to_spec=True,
        design_free=False,
        valves_free=False,
        label="desired_flows",
    )
    net = network or build_network(case.network)
    m = build_model(case, spec, net)
    if water_inlet_C is not None:
        m.T_w_in.fix(water_inlet_C)
    report = solve_model(m, settings)
    return Solution.from_model(m, report, spec.label)


def hydraulic_only_optimization(
    case: CaseStudy,
    target_flows_kg_s: dict[str, float],
    *,
    budget: float | None = None,
    hot_flow_factor: float | None = None,
    settings: SolverSettings | None = None,
    network: Network | None = None,
    warm_start: Solution | None = None,
    label: str = "hydraulic_only",
    **spec_overrides,
) -> Solution:
    """Minimize the squared deviation between cooler flow rates and targets (Lee et al. premise).

    The thermal model is kept only to *evaluate* the penalties of the solution.
    """
    factor = case.scenarios.hot_flow_increase_factor if hot_flow_factor is None else hot_flow_factor
    spec = ProblemSpec(
        hot_flow_factor=factor,
        budget=budget,
        objective="flow_deviation",
        target_flows_kg_s=dict(target_flows_kg_s),
        label=label,
        **spec_overrides,
    )
    return _run(case, spec, settings, network, warm_start)


def linspace_budgets(max_budget: float, steps: int) -> list[float]:
    return [max_budget * i / steps for i in range(steps + 1)]


def penalty_grid(base_penalty: float, max_factor: float, steps: int) -> list[float]:
    return [base_penalty * max_factor * i / steps for i in range(steps + 1)]


def existing_design(case: CaseStudy) -> Design:
    return Design.from_case(case)


__all__ = [
    "budget_sweep",
    "desired_water_flow_rates",
    "existing_design",
    "hydraulic_only_optimization",
    "linspace_budgets",
    "load_warm_start",
    "optimize_debottlenecking",
    "penalty_grid",
    "penalty_sweep",
    "simulate_existing_network",
]


def _unused(_: Iterable) -> None:  # pragma: no cover
    pass
