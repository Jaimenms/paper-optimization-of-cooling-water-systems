"""Render every table and figure of the paper from a result directory."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from coolingnet.config.schema import CaseStudy
from coolingnet.reporting import figures as fig_
from coolingnet.reporting import tables as tab
from coolingnet.reporting.network_plot import plot_network
from coolingnet.workflow.store import ResultStore


def export_all(
    case: CaseStudy, results_dir: str | Path, out_dir: str | Path, *, fmt: str = "png"
) -> list[Path]:
    store = ResultStore(results_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def save_fig(fig, name: str) -> None:
        p = out / f"{name}.{fmt}"
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        written.append(p)

    def save_table(df, name: str) -> None:
        p = out / f"{name}.csv"
        df.to_csv(p)
        written.append(p)
        p2 = out / f"{name}.md"
        p2.write_text(df.to_markdown())
        written.append(p2)

    # data tables
    save_table(tab.table_circuits(case), "table01_circuits")
    save_table(tab.table_pipes(case), "table02_pipes")
    save_table(tab.table_pumps(case), "table03_pumps")
    save_table(tab.table_pump_cost_parameters(case), "table04_pump_cost")
    save_table(tab.table_thermal_tasks(case), "table05_thermal_tasks")
    save_table(tab.table_exchanger_design(case), "table06_exchanger_design")
    save_table(tab.table_problem_parameters(case), "table07_parameters")
    fig, ax = plt.subplots(figsize=(11, 5))
    plot_network(case, ax=ax)
    save_fig(fig, "fig01_network")

    have = store.index()
    if "initial" in have and "current" in have:
        ini, cur = store.load("initial"), store.load("current")
        save_table(tab.table_heat_exchangers_performance(case, ini, cur), "table08_performance")
        if "no_budget" in have:
            nb = store.load("no_budget")
            save_table(tab.table_no_budget(cur, nb), "table09_no_budget")
        cases = {name: store.load(name) for name in case.scenarios.penalty_cases if name in have}
        if cases:
            save_table(tab.table_unlimited_budget(cur, cases), "table10_unlimited")
            for i, (name, s) in enumerate(cases.items(), start=2):
                fig, ax = plt.subplots(figsize=(6.5, 5.5))
                fig_.plot_diameter_dotchart(case, s, ax=ax, label=name)
                save_fig(fig, f"fig{i:02d}_diameters_{name}")
        budget_cases = {
            name: store.load(f"budget_{name}")
            for name in case.scenarios.budget_cases
            if f"budget_{name}" in have
        }
        if budget_cases:
            save_table(tab.table_budget_cases(budget_cases), "table11_budget_cases")
            for name, s in budget_cases.items():
                fig, ax = plt.subplots(figsize=(6.5, 5.5))
                fig_.plot_diameter_dotchart(case, s, ax=ax, label=f"Case {name}")
                save_fig(fig, f"fig05_06_diameters_{name}")
        if store.has_sweep("penalty_sweep"):
            fig, ax = plt.subplots(figsize=(6.5, 5))
            fig_.plot_penalty_sweep(
                store.load_sweep("penalty_sweep"),
                ax=ax,
                markers={k: v for k, v in case.scenarios.penalty_cases.items()},
            )
            save_fig(fig, "fig04_penalty_sweep")
        if store.has_sweep("budget_sweep"):
            sweep = store.load_sweep("budget_sweep")
            unl = cases.get(next(iter(case.scenarios.penalty_cases))) if cases else None
            fig, ax = plt.subplots(figsize=(6.5, 5))
            fig_.plot_budget_costs(
                sweep,
                ax=ax,
                current_penalty=cur.costs["cpen"],
                unlimited=unl,
                markers={f"Case {k}": v for k, v in case.scenarios.budget_cases.items()},
            )
            save_fig(fig, "fig07_budget_costs")
            fig, ax = plt.subplots(figsize=(6.5, 5))
            fig_.plot_budget_interventions(
                sweep,
                ax=ax,
                unlimited=unl,
                markers={f"Case {k}": v for k, v in case.scenarios.budget_cases.items()},
            )
            save_fig(fig, "fig08_budget_interventions")
            written.append(
                fig_.save_budget_animation(case, sweep, out / "video01_budget_animation.gif")
            )
        comparison = {}
        if "no_budget" in have:
            comparison["No Budget"] = store.load("no_budget")
        for name, s in budget_cases.items():
            comparison[f"Case {name}"] = s
        first_case = next(iter(case.scenarios.penalty_cases), None)
        if first_case in cases:
            comparison[
                f"Case {first_case[-1] if first_case.startswith('case') else first_case}"
            ] = cases[first_case]
        if comparison:
            fig, ax = plt.subplots(figsize=(6.5, 4.5))
            fig_.plot_comparison_bars(comparison, quantity="objective", ax=ax)
            save_fig(fig, "fig09_objective_comparison")
            fig, ax = plt.subplots(figsize=(6.5, 4.5))
            fig_.plot_comparison_bars(
                comparison, quantity="penalty_reduction", reference_penalty=cur.costs["cpen"], ax=ax
            )
            save_fig(fig, "fig10_penalty_reduction")
            save_table(tab.table_costs(comparison), "table_costs_comparison")
        if "desired_flows" in have and "hydraulic_only" in have:
            des, hyd = store.load("desired_flows"), store.load("hydraulic_only")
            save_table(tab.table_hydraulic_only(cur, des, hyd), "table12_hydraulic_only")
            fig, ax = plt.subplots(figsize=(6.5, 5.5))
            fig_.plot_diameter_dotchart(case, hyd, ax=ax, label="Purely hydraulic")
            save_fig(fig, "fig11_diameters_hydraulic_only")
    return written
