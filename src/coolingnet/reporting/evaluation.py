"""`coolingnet eval`: compare the cached results with the published values.

Three groups of comparisons are made from the JSON cache written by `coolingnet run`:

* the result tables of the paper (Tables 8-12) and the values printed in Figs. 9-10, read
  from ``data/reference/published_values.json`` (:mod:`coolingnet.reporting.paper_reference`);
* the designs shown in Figs. 2-3, 5-6 and 11 (pump option and substituted pipes);
* the values displayed in the listings of the original GAMS runs (``legacy/gams``), parsed
  into ``data/reference/d4_*.json`` by ``scripts/parse_gams_lst.py``.

:func:`evaluate` returns an :class:`Evaluation`; :func:`write_report` writes a markdown report
and CSV files with the deviations (``results/eval/`` by default).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from coolingnet import __version__
from coolingnet.config.schema import CaseStudy
from coolingnet.optimization.results import Solution
from coolingnet.paths import reference_dir
from coolingnet.reporting import paper_reference as REF
from coolingnet.reporting import tables as tab
from coolingnet.workflow.store import ResultStore

KUSD = 1e-3

# Absolute tolerances in the printed units (half a unit of the last printed digit, plus a
# margin for the solver tolerances): a value is "reproduced" when |computed - published| <= tol.
TOL = {
    "C": 0.011,
    "kg/s": 0.015,
    "m": 0.015,
    "kUSD/y": 0.015,
    "%": 0.02,
    "kg2/s2": 1.0,
    # original GAMS listings (3 decimals printed, USD/y)
    "USD/y": 0.5,
    "C (gams)": 0.0015,
    "kg/s (gams)": 0.0015,
}

# Explanations of the deviations that are not errors (details in docs/reproduction.md).
NOTES = {
    "Table 10 - Case 2": "different local optimum of the non-convex MINLP: objective 0.01 % "
    "lower than published (189.76 vs 189.78 kUSD/y), pump 4 and ten pipes as published but a "
    "different pipe set; flows within 0.45 kg/s",
    "Table 11 - Case 1B": "objective 0.02 % lower than published (85.03 vs 85.04 kUSD/y): "
    "pump 4 plus two small pipe substitutions (1 -> 14 in, 18 -> 2.5 in) instead of the pump "
    "alone; E-105 valve 1.02 vs 1.62 m",
    "Table 12": "lower flow-deviation objective than published (523.3 vs 524.0 kg2/s2) with the "
    "published pump and enlarged pipes plus three downsized small pipes; the E-105 flow (0.02 vs "
    "0.07 kg/s) sits where its penalty is very sensitive (341.8 vs 320.0 kUSD/y)",
    "Fig. 9": "Case 1B 0.02 % lower (see Table 11)",
    "Fig. 10": "Case 1B: 26.76 vs 26.48 % (penalty 53.98 vs 54.20 kUSD/y, see Table 11)",
    "GAMS case2": "same local-optimum difference as Table 10 - Case 2",
    "GAMS budget_sweep": "different local optimum: objective 4.5 USD/y (0.005 %) below the GAMS "
    "run with a different set of small pipe substitutions",
}

# Remarks on the designs of Figs. 2, 3, 5, 6 and 11 that differ from the published ones.
DESIGN_NOTES = {
    "Case 1B": "two small pipes added to the pump substitution (objective 0.02 % lower)",
    "Case 1C": "pipes 5 and 6 have the same length, diameter and flow: interchangeable, "
    "identical cost and flows",
    "Purely hydraulic (budget 1A)": "same pump and enlarged pipes as published; pipes 13, 14 "
    "and 18 additionally downsized (flow-deviation objective 523.3 vs 524.0 kg2/s2)",
}


@dataclass
class Deviation:
    item: str
    quantity: str
    row: str
    published: float
    computed: float | None
    unit: str

    @property
    def tolerance(self) -> float:
        return TOL[self.unit]

    @property
    def deviation(self) -> float | None:
        if self.computed is None or _isnan(self.computed):
            return None
        return float(self.computed - self.published)

    @property
    def deviation_pct(self) -> float | None:
        d = self.deviation
        if d is None or abs(self.published) < 1e-12:
            return None
        return 100.0 * d / abs(self.published)

    @property
    def ok(self) -> bool:
        d = self.deviation
        return d is not None and abs(d) <= self.tolerance

    def as_record(self) -> dict:
        return {
            "item": self.item,
            "quantity": self.quantity,
            "row": self.row,
            "unit": self.unit,
            "published": self.published,
            "this_work": self.computed,
            "deviation": self.deviation,
            "deviation_pct": self.deviation_pct,
            "tolerance": self.tolerance,
            "within_tolerance": self.ok,
        }


def _isnan(x) -> bool:
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return True


@dataclass
class Evaluation:
    results_dir: Path
    deviations: list[Deviation] = field(default_factory=list)
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)  # side-by-side tables
    designs: pd.DataFrame | None = None
    missing: list[str] = field(default_factory=list)  # paper items without cached runs
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    # ------------------------------------------------------------------ queries
    def items(self) -> list[str]:
        seen: dict[str, None] = {}
        for d in self.deviations:
            seen.setdefault(d.item, None)
        return list(seen)

    def deviations_frame(self) -> pd.DataFrame:
        return pd.DataFrame([d.as_record() for d in self.deviations])

    def summary(self) -> pd.DataFrame:
        """One line per paper item: number of values, largest deviation, status and note."""
        rows = []
        for item in self.items():
            devs = [d for d in self.deviations if d.item == item]
            with_values = [d for d in devs if d.deviation is not None]
            if not with_values:
                rows.append(
                    {
                        "item": item,
                        "values": len(devs),
                        "max_abs_dev": None,
                        "max_rel_dev_pct": None,
                        "status": "missing",
                        "note": "no cached result",
                    }
                )
                continue
            worst = max(with_values, key=lambda d: abs(d.deviation) / d.tolerance)
            max_abs = abs(worst.deviation)
            rel = [abs(d.deviation_pct) for d in with_values if d.deviation_pct is not None]
            n_bad = sum(1 for d in with_values if not d.ok)
            if n_bad == 0:
                status = "reproduced"
            else:
                status = f"{n_bad} of {len(with_values)} values beyond tolerance (max |dev| {max_abs:.3g} {worst.unit}, {worst.quantity} {worst.row})"
            rows.append(
                {
                    "item": item,
                    "values": len(with_values),
                    "max_abs_dev": max_abs,
                    "max_rel_dev_pct": max(rel) if rel else None,
                    "status": status,
                    "note": NOTES.get(item, ""),
                }
            )
        return pd.DataFrame(rows).set_index("item")

    @property
    def all_reproduced(self) -> bool:
        return all(d.ok for d in self.deviations if d.deviation is not None)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _he(sol: Solution) -> pd.DataFrame:
    return sol.exchangers_df()


def _changed_pipes(sol: Solution) -> dict[str, float]:
    return {
        str(e["id"]): float(e["diameter_in"])
        for e in sol.edges
        if e["kind"] == "pipe" and e.get("changed")
    }


def _fmt_pipes(d: dict[str, float]) -> str:
    return (
        ", ".join(f"{k}: {v:g} in" for k, v in sorted(d.items(), key=lambda kv: int(kv[0])))
        or "none"
    )


def _side_by_side(
    paper: pd.DataFrame, computed: pd.DataFrame, columns: list[str] | None = None
) -> pd.DataFrame:
    return REF.compare(paper, computed, {c: c for c in (columns or paper.columns)})


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
def evaluate(
    case: CaseStudy, results_dir: str | Path, *, gams_reference: str | Path | None = None
) -> Evaluation:
    """Compare the cached runs in `results_dir` with the published values."""
    store = ResultStore(results_dir)
    ev = Evaluation(results_dir=Path(results_dir))

    def load(name: str) -> Solution | None:
        return store.load(name) if store.has(name) else None

    initial, current = load("initial"), load("current")
    tags = REF.HE_TAGS

    def add_columns(
        item: str,
        paper: pd.DataFrame,
        computed: pd.DataFrame | None,
        units: dict[str, str],
        columns: list[str] | None = None,
    ) -> None:
        cols = columns or list(paper.columns)
        for col in cols:
            unit = units[col]
            for tag in tags:
                val = None if computed is None else float(computed.loc[tag, col])
                ev.deviations.append(
                    Deviation(item, col, tag, float(paper.loc[tag, col]), val, unit)
                )
        if computed is not None:
            ev.frames[item] = _side_by_side(paper, computed, cols)

    # ---------------------------------------------------------------- Table 8
    item = "Table 8"
    units8 = {c: ("kUSD/y" if "penalty" in c else "C") for c in REF.TABLE8.columns}
    if initial is not None and current is not None:
        t8 = tab.table_heat_exchangers_performance(case, initial, current)
        add_columns(item, REF.TABLE8, t8, units8)
        ev.deviations.append(
            Deviation(
                item,
                "Current condition penalty (kUSD/y)",
                "Total",
                REF.TABLE8_TOTAL_PENALTY,
                float(t8.loc["Total", "Current condition penalty (kUSD/y)"]),
                "kUSD/y",
            )
        )
    else:
        add_columns(item, REF.TABLE8, None, units8)
        ev.missing.append(item)

    # ---------------------------------------------------------------- Table 9
    item = "Table 9"
    units9 = {
        "Current cooling water flow rate (kg/s)": "kg/s",
        "Optimal cooling water flow rate (kg/s)": "kg/s",
        "Valve head loss (m)": "m",
        "Penalty (kUSD/y)": "kUSD/y",
        "Penalty variation (%)": "%",
    }
    no_budget = load("no_budget")
    if current is not None and no_budget is not None:
        t9 = tab.table_no_budget(current, no_budget)
        add_columns(item, REF.TABLE9, t9, units9)
        tot = REF.TABLE9_TOTALS
        ev.deviations += [
            Deviation(
                item,
                "Current cooling water flow rate (kg/s)",
                "Total",
                tot["current_flow"],
                float(t9.loc["Total", "Current cooling water flow rate (kg/s)"]),
                "kg/s",
            ),
            Deviation(
                item,
                "Optimal cooling water flow rate (kg/s)",
                "Total",
                tot["optimal_flow"],
                float(t9.loc["Total", "Optimal cooling water flow rate (kg/s)"]),
                "kg/s",
            ),
            Deviation(
                item,
                "Penalty (kUSD/y)",
                "Total",
                tot["penalty"],
                float(t9.loc["Total", "Penalty (kUSD/y)"]),
                "kUSD/y",
            ),
            Deviation(
                item,
                "Penalty variation (%)",
                "Total",
                tot["penalty_variation"],
                float(t9.loc["Total", "Penalty variation (%)"]),
                "%",
            ),
            Deviation(
                item,
                "Operating cost after (kUSD/y)",
                "text",
                REF.NO_BUDGET_TEXT["operating_after"],
                no_budget.costs["cope"] * KUSD,
                "kUSD/y",
            ),
            Deviation(
                item,
                "Operating cost before (kUSD/y)",
                "text",
                REF.NO_BUDGET_TEXT["operating_before"],
                current.costs["cope"] * KUSD,
                "kUSD/y",
            ),
            Deviation(
                item,
                "Total cost reduction (%)",
                "text",
                REF.NO_BUDGET_TEXT["total_reduction_pct"],
                (
                    1
                    - (no_budget.costs["cpen"] + no_budget.costs["cope"])
                    / (current.costs["cpen"] + current.costs["cope"])
                )
                * 100,
                "%",
            ),
        ]
    else:
        add_columns(item, REF.TABLE9, None, units9)
        ev.missing.append(item)

    # ---------------------------------------------------------------- Table 10
    design_rows = []
    for name, label in (("case1", "Case 1"), ("case2", "Case 2")):
        item = f"Table 10 - {label}"
        sol = load(name)
        cols = [c for c in REF.TABLE10.columns if label in c]
        units10 = {
            c: ("kg/s" if "flow" in c else "m" if "head loss" in c else "kUSD/y") for c in cols
        }
        if sol is not None and current is not None:
            df = _he(sol)
            computed = pd.DataFrame(
                {
                    f"Optimal flow {label} (kg/s)": df["k_kg_s"],
                    f"Valve head loss {label} (m)": df["valve_head_loss_m"],
                    f"Penalty {label} (kUSD/y)": df["penalty_USD_y"] * KUSD,
                }
            )
            add_columns(item, REF.TABLE10, computed, units10, cols)
            tot = REF.TABLE10_TOTALS[name]
            ev.deviations += [
                Deviation(
                    item,
                    f"Optimal flow {label} (kg/s)",
                    "Total",
                    tot["flow"],
                    float(df["k_kg_s"].sum()),
                    "kg/s",
                ),
                Deviation(
                    item,
                    f"Penalty {label} (kUSD/y)",
                    "Total",
                    tot["penalty"],
                    float(df["penalty_USD_y"].sum() * KUSD),
                    "kUSD/y",
                ),
            ]
            pub = REF.UNLIMITED_DESIGNS[name]
            changed = _changed_pipes(sol)
            if "pipes_changed" in pub:
                pub_pipes, match = (
                    _fmt_pipes(pub["pipes_changed"]),
                    changed == {k: float(v) for k, v in pub["pipes_changed"].items()},
                )
            else:
                pub_pipes, match = (
                    f"{pub['n_pipes_changed']} pipes",
                    len(changed) == pub["n_pipes_changed"],
                )
            match = match and sol.pump_options() == {
                str(u.id): pub["pump"] for u in case.network.pumps
            }
            design_rows.append(
                {
                    "figure": "Fig. 2" if name == "case1" else "Fig. 3",
                    "run": label,
                    "pump (paper)": pub["pump"],
                    "pump (this work)": "/".join(sol.pump_options().values()),
                    "pipes changed (paper)": pub_pipes,
                    "pipes changed (this work)": _fmt_pipes(changed),
                    "match": match,
                }
            )
        else:
            add_columns(item, REF.TABLE10, None, units10, cols)
            ev.missing.append(item)

    # ---------------------------------------------------------------- Table 11
    for name in ("1A", "1B", "1C"):
        item = f"Table 11 - Case {name}"
        sol = load(f"budget_{name}")
        cols = [c for c in REF.TABLE11.columns if f" {name} " in c]
        units11 = {
            c: ("kg/s" if "flow" in c else "m" if "head loss" in c else "kUSD/y") for c in cols
        }
        if sol is not None:
            df = _he(sol)
            computed = pd.DataFrame(
                {
                    f"Optimal flow {name} (kg/s)": df["k_kg_s"],
                    f"Valve head loss {name} (m)": df["valve_head_loss_m"],
                    f"Penalty {name} (kUSD/y)": df["penalty_USD_y"] * KUSD,
                }
            )
            add_columns(item, REF.TABLE11, computed, units11, cols)
            tot = REF.TABLE11_TOTALS[name]
            ev.deviations += [
                Deviation(
                    item,
                    f"Optimal flow {name} (kg/s)",
                    "Total",
                    tot["flow"],
                    float(df["k_kg_s"].sum()),
                    "kg/s",
                ),
                Deviation(
                    item,
                    f"Penalty {name} (kUSD/y)",
                    "Total",
                    tot["penalty"],
                    float(df["penalty_USD_y"].sum() * KUSD),
                    "kUSD/y",
                ),
            ]
            pub = REF.BUDGET_DESIGNS[name]
            changed = _changed_pipes(sol)
            match = changed == {
                k: float(v) for k, v in pub["pipes_changed"].items()
            } and sol.pump_options() == {str(u.id): pub["pump"] for u in case.network.pumps}
            design_rows.append(
                {
                    "figure": {"1A": "Fig. 5", "1B": "text", "1C": "Fig. 6"}[name],
                    "run": f"Case {name}",
                    "pump (paper)": pub["pump"],
                    "pump (this work)": "/".join(sol.pump_options().values()),
                    "pipes changed (paper)": _fmt_pipes(pub["pipes_changed"]),
                    "pipes changed (this work)": _fmt_pipes(changed),
                    "match": match,
                }
            )
        else:
            add_columns(item, REF.TABLE11, None, units11, cols)
            ev.missing.append(item)

    # ---------------------------------------------------------------- Table 12
    item = "Table 12"
    units12 = {
        "Current cooling water flow rate (kg/s)": "kg/s",
        "Desired cooling water flow rate (kg/s)": "kg/s",
        "Optimal cooling water flow rate (kg/s)": "kg/s",
        "Valve head loss (m)": "m",
        "Penalty (kUSD/y)": "kUSD/y",
    }
    desired, hyd = load("desired_flows"), load("hydraulic_only")
    if current is not None and desired is not None and hyd is not None:
        t12 = tab.table_hydraulic_only(current, desired, hyd)
        add_columns(item, REF.TABLE12, t12, units12)
        tot = REF.TABLE12_TOTALS
        targets = {x["tag"]: x["k_kg_s"] for x in desired.exchangers}
        ev.deviations += [
            Deviation(
                item,
                "Desired cooling water flow rate (kg/s)",
                "Total",
                tot["desired_flow"],
                float(t12.loc["Total", "Desired cooling water flow rate (kg/s)"]),
                "kg/s",
            ),
            Deviation(
                item,
                "Optimal cooling water flow rate (kg/s)",
                "Total",
                tot["optimal_flow"],
                float(t12.loc["Total", "Optimal cooling water flow rate (kg/s)"]),
                "kg/s",
            ),
            Deviation(
                item,
                "Penalty (kUSD/y)",
                "Total",
                tot["penalty"],
                float(t12.loc["Total", "Penalty (kUSD/y)"]),
                "kUSD/y",
            ),
            Deviation(
                item,
                "Flow deviation, current (kg2/s2)",
                "text",
                REF.LEE_FLOW_DEVIATION["current_kg2_s2"],
                tab.flow_deviation(current, targets),
                "kg2/s2",
            ),
            Deviation(
                item,
                "Flow deviation, optimal (kg2/s2)",
                "text",
                REF.LEE_FLOW_DEVIATION["optimal_kg2_s2"],
                tab.flow_deviation(hyd, targets),
                "kg2/s2",
            ),
        ]
        pub = REF.LEE_DESIGN
        changed = _changed_pipes(hyd)
        match = changed == {
            k: float(v) for k, v in pub["pipes_changed"].items()
        } and hyd.pump_options() == {str(u.id): pub["pump"] for u in case.network.pumps}
        design_rows.append(
            {
                "figure": "Fig. 11",
                "run": "Purely hydraulic (budget 1A)",
                "pump (paper)": pub["pump"],
                "pump (this work)": "/".join(hyd.pump_options().values()),
                "pipes changed (paper)": _fmt_pipes(pub["pipes_changed"]),
                "pipes changed (this work)": _fmt_pipes(changed),
                "match": match,
            }
        )
    else:
        add_columns(item, REF.TABLE12, None, units12)
        ev.missing.append(item)

    # ---------------------------------------------------------------- Figs. 9-10
    comparison: dict[str, Solution | None] = {
        "No Budget": no_budget,
        "Case 1A": load("budget_1A"),
        "Case 1B": load("budget_1B"),
        "Case 1C": load("budget_1C"),
        "Case 1": load("case1"),
    }
    ref_pen = current.costs["cpen"] if current is not None else None
    fig_rows = {}
    for label, pub_obj in REF.FIG9_OBJECTIVE_KUSD.items():
        sol = comparison.get(label)
        obj = None if sol is None else sol.costs["total_cost"] * KUSD
        red = (
            None
            if sol is None or ref_pen is None
            else (ref_pen - sol.costs["cpen"]) / ref_pen * 100.0
        )
        ev.deviations.append(
            Deviation("Fig. 9", "Objective function (kUSD/y)", label, pub_obj, obj, "kUSD/y")
        )
        ev.deviations.append(
            Deviation(
                "Fig. 10",
                "Penalty reduction (%)",
                label,
                REF.FIG10_PENALTY_REDUCTION_PCT[label],
                red,
                "%",
            )
        )
        fig_rows[label] = {
            "Objective (kUSD/y) [paper]": pub_obj,
            "Objective (kUSD/y) [this work]": obj,
            "Penalty reduction (%) [paper]": REF.FIG10_PENALTY_REDUCTION_PCT[label],
            "Penalty reduction (%) [this work]": red,
        }
    if any(v is not None for v in comparison.values()):
        ev.frames["Figs. 9-10"] = pd.DataFrame.from_dict(fig_rows, orient="index").rename_axis(
            "Run"
        )
    if any(v is None for v in comparison.values()):
        ev.missing.append("Figs. 9-10")

    if design_rows:
        ev.designs = pd.DataFrame(design_rows).set_index("run")
        ev.designs["note"] = [
            "" if match else DESIGN_NOTES.get(run, "")
            for run, match in zip(ev.designs.index, ev.designs["match"], strict=True)
        ]

    # ---------------------------------------------------------------- original GAMS listings
    _compare_with_gams(ev, case, store, Path(gams_reference) if gams_reference else reference_dir())
    return ev


# GAMS display group -> cached run.  (file, group, run name, sweep budget)
GAMS_RUNS = [
    # (file, display group, cached run, sweep budget, compared quantity groups)
    ("d4_part2_initial.json", "850", "initial", None, ("costs", "tower", "flows")),
    ("d4_part2_actual.json", "824", "current", None, ("costs", "tower", "flows")),
    ("d4_part3.json", "817", "case1", None, ("costs", "flows")),
    ("d4_part3.json", "852", "case2", None, ("costs", "flows")),
    # the temperatures displayed with the desired flow rates belong to the simulation step at
    # the design flows (group "sim1"); only the flow rates are the Table 12 "desired" column
    ("d4_part2_actual_simulation.json", "768", "desired_flows", None, ("flows",)),
    ("d4_part4_case01_redo.json", "827", "budget_sweep", 2437.5, ("costs", "flows")),
]


def _compare_with_gams(ev: Evaluation, case: CaseStudy, store: ResultStore, ref_dir: Path) -> None:
    edge_tag = {str(e.id): e.tag for e in case.network.heat_exchangers}
    rows = []
    for fname, group, run, budget, groups in GAMS_RUNS:
        path = ref_dir / fname
        if not path.exists():
            continue
        syms = json.loads(path.read_text(encoding="utf-8")).get(group, {}).get("symbols", {})
        sol: Solution | None = None
        if budget is None:
            sol = store.load(run) if store.has(run) else None
            label = run
        else:
            label = f"budget_sweep (B = {budget:g} USD/y)"
            if store.has_sweep(run):
                sol = next(
                    (
                        s
                        for s in store.load_sweep(run)
                        if s.spec.get("budget") is not None
                        and abs(s.spec["budget"] - budget) < 1e-6
                    ),
                    None,
                )
        item = f"GAMS {run}" if budget is None else "GAMS budget_sweep"
        if sol is None:
            ev.missing.append(item)
        for key, unit in (
            ("fob", "USD/y"),
            ("cope", "USD/y"),
            ("cpipe", "USD/y"),
            ("cpump", "USD/y"),
            ("cpen", "USD/y"),
        ):
            if "costs" in groups and key in syms and not isinstance(syms[key], dict):
                comp = None if sol is None else float(sol.costs[key])
                ev.deviations.append(Deviation(item, key, label, float(syms[key]), comp, unit))
                rows.append(
                    {
                        "item": item,
                        "run": label,
                        "quantity": key,
                        "unit": "USD/y",
                        "gams": syms[key],
                        "this_work": comp,
                    }
                )
        for key, field_, unit in (
            ("T_w_base", "T_w_in_C", "C (gams)"),
            ("T_w_feed", "T_w_feed_C", "C (gams)"),
        ):
            if "tower" in groups and key in syms and not isinstance(syms[key], dict):
                comp = None if sol is None else float(sol.tower[field_])
                ev.deviations.append(Deviation(item, key, label, float(syms[key]), comp, unit))
                rows.append(
                    {
                        "item": item,
                        "run": label,
                        "quantity": key,
                        "unit": "C",
                        "gams": syms[key],
                        "this_work": comp,
                    }
                )
        k_edge = syms.get("k_edge", {})
        if "flows" in groups and isinstance(k_edge, dict):
            he = None if sol is None else sol.exchangers_df()
            for eid, tag in edge_tag.items():
                if eid in k_edge:
                    comp = None if he is None else float(he.loc[tag, "k_kg_s"])
                    ev.deviations.append(
                        Deviation(
                            item, f"k {tag} (kg/s)", label, float(k_edge[eid]), comp, "kg/s (gams)"
                        )
                    )
                    rows.append(
                        {
                            "item": item,
                            "run": label,
                            "quantity": f"k {tag}",
                            "unit": "kg/s",
                            "gams": k_edge[eid],
                            "this_work": comp,
                        }
                    )
    if rows:
        df = pd.DataFrame(rows)
        df["deviation"] = df["this_work"] - df["gams"]
        ev.frames["Original GAMS listings"] = df.set_index(["run", "quantity"])


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
FRAME_FILES = {
    "Table 8": "table08.csv",
    "Table 9": "table09.csv",
    "Table 10 - Case 1": "table10_case1.csv",
    "Table 10 - Case 2": "table10_case2.csv",
    "Table 11 - Case 1A": "table11_case1A.csv",
    "Table 11 - Case 1B": "table11_case1B.csv",
    "Table 11 - Case 1C": "table11_case1C.csv",
    "Table 12": "table12.csv",
    "Figs. 9-10": "figures09_10.csv",
    "Original GAMS listings": "gams_listings.csv",
}


def write_report(ev: Evaluation, out_dir: str | Path) -> list[Path]:
    """Write ``report.md``, ``summary.csv``, ``deviations.csv``, ``designs.csv`` and one CSV per item."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def save(df: pd.DataFrame, name: str) -> None:
        p = out / name
        df.to_csv(p)
        written.append(p)

    summary = ev.summary()
    save(summary, "summary.csv")
    save(ev.deviations_frame(), "deviations.csv")
    if ev.designs is not None:
        save(ev.designs, "designs.csv")
    for item, df in ev.frames.items():
        save(df, FRAME_FILES.get(item, item.lower().replace(" ", "_").replace(".", "") + ".csv"))

    lines = [
        "# coolingnet - evaluation against the published values",
        "",
        f"Paper: {REF.citation()}",
        "",
        f"Results directory: `{ev.results_dir}` - evaluated {ev.created_at} with coolingnet {__version__}.",
        "",
        "A value is *reproduced* when |this work - published| is within the tolerance of the printed",
        "precision (see `deviations.csv`; tolerances in `coolingnet.reporting.evaluation.TOL`).",
        "Deviations that are not errors are explained in `docs/reproduction.md`.",
        "",
        "## Summary",
        "",
        summary.reset_index().to_markdown(index=False, floatfmt=".4g"),
        "",
    ]
    if ev.missing:
        lines += [
            "Items without cached results (run `make run`): " + ", ".join(sorted(set(ev.missing))),
            "",
        ]
    if ev.designs is not None:
        lines += [
            "## Designs (Figs. 2, 3, 5, 6, 11)",
            "",
            ev.designs.reset_index().to_markdown(index=False),
            "",
        ]
    for item, df in ev.frames.items():
        lines += [f"## {item}", "", df.reset_index().to_markdown(index=False, floatfmt=".3f"), ""]
    p = out / "report.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    written.append(p)
    return written


__all__ = ["Deviation", "Evaluation", "NOTES", "TOL", "evaluate", "write_report"]
