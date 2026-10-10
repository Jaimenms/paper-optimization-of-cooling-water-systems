"""Run all the scenarios of the paper (Sections 3.2-3.7) with caching.

Run names (keys of the result store):

initial, current            Table 8 (simulation of the existing network)
no_budget                   Table 9, Figs. 9-10
case1, case2                Table 10, Figs. 2-3
budget_1A, budget_1B, ...   Table 11, Figs. 5-6 (one per `scenarios.budget_cases`)
budget_sweep/               Figs. 7-8 and the animation (Video 1)
penalty_sweep/              Fig. 4
desired_flows               Table 12, "desired" column
hydraulic_only              Table 12, Fig. 11
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from coolingnet.config.schema import CaseStudy
from coolingnet.network.graph import Network, build_network
from coolingnet.optimization.problems import (
    budget_sweep,
    desired_water_flow_rates,
    hydraulic_only_optimization,
    linspace_budgets,
    optimize_debottlenecking,
    penalty_grid,
    penalty_sweep,
    simulate_existing_network,
)
from coolingnet.optimization.results import Solution
from coolingnet.optimization.solvers import SolverSettings
from coolingnet.workflow.store import ResultStore

log = logging.getLogger(__name__)

STAGES = (
    "simulations",
    "no_budget",
    "unlimited",
    "budget_cases",
    "budget_sweep",
    "penalty_sweep",
    "literature",
)


@dataclass
class PipelineConfig:
    results_dir: Path = Path("results")
    solver: SolverSettings = field(default_factory=SolverSettings)
    force: bool = False  # re-run even if a cached result exists
    stages: tuple[str, ...] = STAGES
    budget_steps: int | None = None  # override scenarios.budget_sweep.steps
    penalty_steps: int | None = None
    progress: Callable[[str], None] | None = None


class PaperPipeline:
    """Orchestrates the runs of the paper; every result is cached in `results_dir`."""

    def __init__(self, case: CaseStudy, config: PipelineConfig | None = None):
        self.case = case
        self.config = config or PipelineConfig()
        self.store = ResultStore(self.config.results_dir)
        self.network: Network = build_network(case.network)

    # ------------------------------------------------------------ helpers
    def _say(self, msg: str) -> None:
        log.info(msg)
        if self.config.progress:
            self.config.progress(msg)

    def _cached(self, name: str, runner: Callable[[], Solution]) -> Solution:
        if not self.config.force and self.store.has(name):
            self._say(f"[cached] {name}")
            return self.store.load(name)
        self._say(f"[solve ] {name} ...")
        sol = runner()
        self.store.save(name, sol)
        self._say(f"[done  ] {name}: {sol.report['termination']} fob={sol.costs['fob']:.1f} gap={sol.report.get('gap')} t={sol.report['time_s']:.0f}s")
        return sol

    def _cached_sweep(self, name: str, values: list[float], runner: Callable[[Callable[[Solution], None]], Iterable[Solution]]) -> list[Solution]:
        if not self.config.force and self.store.has_sweep(name, expected=len(values)):
            self._say(f"[cached] {name} ({len(values)} runs)")
            return self.store.load_sweep(name)
        self._say(f"[solve ] {name}: {len(values)} runs ...")
        d = self.store.sweep_dir(name)
        for old in d.glob("*.json"):
            old.unlink()
        counter = {"i": 0}

        def on_result(sol: Solution) -> None:
            self.store.append_to_sweep(name, sol, counter["i"])
            counter["i"] += 1
            self._say(f"   {name}[{counter['i']}/{len(values)}] {sol.label}: {sol.report['termination']} fob={sol.costs['fob']:.1f} gap={sol.report.get('gap')}")

        sols = list(runner(on_result))
        self.store._update_index(name, None, count=len(sols))
        return sols

    # ------------------------------------------------------------- stages
    @property
    def solver(self) -> SolverSettings:
        return self.config.solver

    def run_simulations(self) -> dict[str, Solution]:
        f = self.case.scenarios.hot_flow_increase_factor
        return {
            "initial": self._cached("initial", lambda: simulate_existing_network(self.case, 1.0, settings=self.solver, network=self.network, label="initial")),
            "current": self._cached("current", lambda: simulate_existing_network(self.case, f, settings=self.solver, network=self.network, label="current")),
        }

    def run_no_budget(self) -> Solution:
        return self._cached("no_budget", lambda: optimize_debottlenecking(self.case, budget=0.0, settings=self.solver, network=self.network, label="no_budget"))

    def run_unlimited(self) -> dict[str, Solution]:
        out = {}
        for name, pen in self.case.scenarios.penalty_cases.items():
            out[name] = self._cached(name, lambda pen=pen, name=name: optimize_debottlenecking(self.case, budget=None, penalty_factor=pen, settings=self.solver, network=self.network, label=name))
        return out

    def run_budget_cases(self) -> dict[str, Solution]:
        out = {}
        base_case = self.store.load("case1") if self.store.has("case1") else None
        for name, b in self.case.scenarios.budget_cases.items():
            key = f"budget_{name}"
            out[key] = self._cached(key, lambda b=b, key=key: optimize_debottlenecking(self.case, budget=b, settings=self.solver, network=self.network, warm_start=base_case, label=key))
        return out

    def run_budget_sweep(self) -> list[Solution]:
        sw = self.case.scenarios.budget_sweep
        steps = self.config.budget_steps or sw.steps
        budgets = linspace_budgets(sw.max_USD_y, steps)
        warm = self.store.load("no_budget") if self.store.has("no_budget") else None
        return self._cached_sweep("budget_sweep", budgets, lambda cb: budget_sweep(self.case, budgets, settings=self.solver, network=self.network, warm_start=warm, on_result=cb))

    def run_penalty_sweep(self) -> list[Solution]:
        sw = self.case.scenarios.penalty_sweep
        steps = self.config.penalty_steps or sw.steps
        base_pen = next(iter(self.case.scenarios.penalty_cases.values()))
        pens = penalty_grid(base_pen, sw.max_factor, steps)
        warm = self.store.load("no_budget") if self.store.has("no_budget") else None
        return self._cached_sweep("penalty_sweep", pens, lambda cb: penalty_sweep(self.case, pens, settings=self.solver, network=self.network, warm_start=warm, on_result=cb))

    def run_literature(self) -> dict[str, Solution]:
        desired = self._cached("desired_flows", lambda: desired_water_flow_rates(self.case, settings=self.solver, network=self.network))
        targets = {row["tag"]: row["k_kg_s"] for row in desired.exchangers}
        first_budget = next(iter(self.case.scenarios.budget_cases.values()))
        warm = self.store.load("no_budget") if self.store.has("no_budget") else None
        hyd = self._cached(
            "hydraulic_only",
            lambda: hydraulic_only_optimization(self.case, targets, budget=first_budget, settings=self.solver, network=self.network, warm_start=warm),
        )
        return {"desired_flows": desired, "hydraulic_only": hyd}

    def run(self) -> dict[str, object]:
        out: dict[str, object] = {}
        stages = self.config.stages
        if "simulations" in stages:
            out.update(self.run_simulations())
        if "no_budget" in stages:
            out["no_budget"] = self.run_no_budget()
        if "unlimited" in stages:
            out.update(self.run_unlimited())
        if "budget_cases" in stages:
            out.update(self.run_budget_cases())
        if "budget_sweep" in stages:
            out["budget_sweep"] = self.run_budget_sweep()
        if "penalty_sweep" in stages:
            out["penalty_sweep"] = self.run_penalty_sweep()
        if "literature" in stages:
            out.update(self.run_literature())
        return out
