"""Pandas versions of Tables 1-12 of the paper."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from coolingnet.config.schema import CaseStudy
from coolingnet.network.graph import Network, build_network
from coolingnet.optimization.results import Solution

KUSD = 1e-3


# --------------------------------------------------------------------------- #
# Problem data (Tables 1-7)
# --------------------------------------------------------------------------- #
def table_circuits(case: CaseStudy, network: Network | None = None) -> pd.DataFrame:
    """Table 1 - hydraulic circuits."""
    net = network or build_network(case.network)
    return pd.DataFrame(net.circuit_table()).set_index("Circuit")


def table_pipes(case: CaseStudy) -> pd.DataFrame:
    """Table 2 - lengths and nominal diameters of the pipe sections."""
    rows = [
        {"Pipe section": p.id, "Length (m)": p.length_m, "Nominal diameter (in)": p.diameter_in}
        for p in case.network.pipes
    ]
    return pd.DataFrame(rows).set_index("Pipe section")


def table_pumps(case: CaseStudy) -> pd.DataFrame:
    """Table 3 - pump head coefficients (head = a0 + a1 q + a2 q^2)."""
    rows = []
    for name, opt in case.pumps.options.items():
        c = opt.coefficients
        rows.append({"Alternative": name, **{f"a{i} ": c[i] for i in reversed(range(len(c)))}})
    return pd.DataFrame(rows).set_index("Alternative")


def table_pump_cost_parameters(case: CaseStudy) -> pd.DataFrame:
    """Table 4 - pump capital cost correlation parameters."""
    pc = case.pumps
    rows = [("F_I", pc.cost_FI), ("F_ms", pc.cost_Fms), ("F_m", pc.cost_Fm)]
    rows += [(f"b{j + 1}", b) for j, b in enumerate(pc.cost_b)]
    rows.append(("q_pu design (m3/s)", pc.design_flow_m3_s))
    return pd.DataFrame(rows, columns=["Factor", "Value"]).set_index("Factor")


def table_thermal_tasks(case: CaseStudy) -> pd.DataFrame:
    """Table 5 - thermal tasks of the coolers."""
    rows = []
    for h in case.resolved_heat_exchangers:
        rows.append(
            {
                "Heat exchanger": h.tag,
                "Flow rate hot/cold (kg/s)": f"{h.hot_flow_design_kg_s:.2f}/{h.water_flow_design_kg_s:.2f}",
                "Inlet temperature hot/cold (C)": f"{h.hot_inlet_C:.2f}/{h.water_inlet_design_C:.2f}",
                "Outlet temperature hot/cold (C)": f"{h.hot_outlet_spec_C:.2f}/{h.water_outlet_design_C:.2f}",
                "Heat capacity hot/cold (J/kg C)": f"{h.cp_hot_J_kgK:.0f}/{case.water.cp_J_kgK:.0f}",
            }
        )
    return pd.DataFrame(rows).set_index("Heat exchanger")


def table_exchanger_design(case: CaseStudy) -> pd.DataFrame:
    """Table 6 - heat exchanger design data."""
    rows = []
    for h in case.resolved_heat_exchangers:
        rows.append(
            {
                "Heat exchanger": h.tag,
                "Area (m2)": h.area_m2,
                "Film coefficient tube/shell (W/m2 C)": f"{h.h_water_design_W_m2K:.0f}/{h.h_hot_design_W_m2K:.0f}",
                "Total fouling factor (1e-4 m2 C/W)": round(h.fouling_m2K_W * 1e4, 2),
                "Design head loss (m)": h.head_loss_design_m,
            }
        )
    return pd.DataFrame(rows).set_index("Heat exchanger")


def table_problem_parameters(case: CaseStudy) -> pd.DataFrame:
    """Table 7 - problem parameters."""
    t, e, w, p = case.cooling_tower, case.economics, case.water, case.pipes
    pen = case.heat_exchanger_defaults.penalty_factor_USD_per_C_y
    rows = [
        ("Cooling water density (kg/m3)", w.density_kg_m3),
        ("Cooling water heat capacity (J/kg C)", w.cp_J_kgK),
        ("Maximum flow velocity (m/s)", p.v_max_m_s),
        ("Minimum flow velocity (m/s)", p.v_min_m_s),
        ("Hazen-Williams parameter c", p.hazen_williams_c),
        ("Pipe cost parameters C1 / m", f"{p.cost_c1} / {p.cost_m}"),
        ("Pump efficiency", case.pumps.efficiency),
        ("Number of operating hours per year (h/y)", e.operating_hours_per_year),
        ("Energy cost (USD/kWh)", e.energy_cost_USD_kWh),
        ("Interest rate", e.interest_rate),
        ("Project horizon (y)", e.project_years),
        ("Elevation difference of the tower (m)", case.network.elevation_difference_m),
        ("Maximum temperature of the cooling water feed (C)", t.max_feed_temperature_C),
        ("Wet bulb temperature (C)", t.wet_bulb_C),
        ("Parameter C_un - Eq. (37)", t.C_un),
        ("Parameter n - Eq. (37)", t.n),
        ("Packing height (m)", t.packing_height_m),
        ("Air mass flow rate (kg/s)", t.air_flow_kg_s),
        ("Penalty weight (kUSD/y C)", pen * KUSD),
        ("Atmospheric air enthalpy (J/kg)", t.atmospheric_air_enthalpy_J_kg),
        ("Merkel quadrature abscissae", ", ".join(f"{a:g}" for a in t.quadrature_points)),
    ]
    return pd.DataFrame(rows, columns=["Parameter", "Value"]).set_index("Parameter")


# --------------------------------------------------------------------------- #
# Results (Tables 8-12)
# --------------------------------------------------------------------------- #
def _he_frame(sol: Solution) -> pd.DataFrame:
    return pd.DataFrame(sol.exchangers).set_index("tag")


def table_heat_exchangers_performance(
    case: CaseStudy, initial: Solution, current: Solution
) -> pd.DataFrame:
    """Table 8 - hot stream outlet temperatures and penalties (design, initial, current)."""
    ini, cur = _he_frame(initial), _he_frame(current)
    df = pd.DataFrame(
        {
            "Design condition (C)": [case.heat_exchanger(t).hot_outlet_spec_C for t in ini.index],
            "Initial condition (C)": ini["T_hot_out_C"].values,
            "Current condition (C)": cur["T_hot_out_C"].values,
            "Current condition penalty (kUSD/y)": cur["penalty_USD_y"].values * KUSD,
        },
        index=ini.index.rename("Heat exchanger"),
    )
    total = pd.DataFrame(
        {"Current condition penalty (kUSD/y)": [df["Current condition penalty (kUSD/y)"].sum()]},
        index=["Total"],
    )
    return pd.concat([df, total])


def table_no_budget(current: Solution, no_budget: Solution) -> pd.DataFrame:
    """Table 9 - optimization results with no available budget."""
    cur, opt = _he_frame(current), _he_frame(no_budget)
    pen_cur, pen_opt = cur["penalty_USD_y"] * KUSD, opt["penalty_USD_y"] * KUSD
    var = (pen_opt - pen_cur) / pen_cur.replace(0, float("nan")) * 100.0
    df = pd.DataFrame(
        {
            "Current cooling water flow rate (kg/s)": cur["k_kg_s"],
            "Optimal cooling water flow rate (kg/s)": opt["k_kg_s"],
            "Valve head loss (m)": opt["valve_head_loss_m"],
            "Penalty (kUSD/y)": pen_opt,
            "Penalty variation (%)": var,
        }
    )
    df.index.name = "Heat exchanger"
    total = pd.DataFrame(
        {
            "Current cooling water flow rate (kg/s)": [cur["k_kg_s"].sum()],
            "Optimal cooling water flow rate (kg/s)": [opt["k_kg_s"].sum()],
            "Penalty (kUSD/y)": [pen_opt.sum()],
            "Penalty variation (%)": [(pen_opt.sum() - pen_cur.sum()) / pen_cur.sum() * 100.0],
        },
        index=["Total"],
    )
    return pd.concat([df, total])


def _joined(values: Sequence[float], fmt: str = "{:.2f}") -> str:
    return "/".join(fmt.format(v) for v in values)


def table_unlimited_budget(current: Solution, cases: dict[str, Solution]) -> pd.DataFrame:
    """Table 10 - unlimited budget, one column group per case (values joined with '/')."""
    cur = _he_frame(current)
    frames = {name: _he_frame(s) for name, s in cases.items()}
    label = "/".join(cases.keys())
    rows = []
    for tag in cur.index:
        rows.append(
            {
                "Heat exchanger": tag,
                "Current cooling water flow rate (kg/s)": round(cur.loc[tag, "k_kg_s"], 2),
                f"Optimal cooling water flow rate (kg/s) {label}": _joined(
                    [f.loc[tag, "k_kg_s"] for f in frames.values()]
                ),
                f"Valve head loss (m) {label}": _joined(
                    [f.loc[tag, "valve_head_loss_m"] for f in frames.values()]
                ),
                f"Penalty (kUSD/y) {label}": _joined(
                    [f.loc[tag, "penalty_USD_y"] * KUSD for f in frames.values()]
                ),
            }
        )
    rows.append(
        {
            "Heat exchanger": "Total",
            "Current cooling water flow rate (kg/s)": round(cur["k_kg_s"].sum(), 2),
            f"Optimal cooling water flow rate (kg/s) {label}": _joined(
                [f["k_kg_s"].sum() for f in frames.values()]
            ),
            f"Valve head loss (m) {label}": "-",
            f"Penalty (kUSD/y) {label}": _joined(
                [f["penalty_USD_y"].sum() * KUSD for f in frames.values()]
            ),
        }
    )
    return pd.DataFrame(rows).set_index("Heat exchanger")


def table_budget_cases(cases: dict[str, Solution]) -> pd.DataFrame:
    """Table 11 - finite budget cases (values joined with '/')."""
    frames = {name: _he_frame(s) for name, s in cases.items()}
    label = "/".join(cases.keys())
    first = next(iter(frames.values()))
    rows = []
    for tag in first.index:
        rows.append(
            {
                "Heat exchanger": tag,
                f"Optimal cooling water flow rate (kg/s) {label}": _joined(
                    [f.loc[tag, "k_kg_s"] for f in frames.values()]
                ),
                f"Valve head loss (m) {label}": _joined(
                    [f.loc[tag, "valve_head_loss_m"] for f in frames.values()]
                ),
                f"Penalty (kUSD/y) {label}": _joined(
                    [f.loc[tag, "penalty_USD_y"] * KUSD for f in frames.values()]
                ),
            }
        )
    rows.append(
        {
            "Heat exchanger": "Total",
            f"Optimal cooling water flow rate (kg/s) {label}": _joined(
                [f["k_kg_s"].sum() for f in frames.values()]
            ),
            f"Valve head loss (m) {label}": "-",
            f"Penalty (kUSD/y) {label}": _joined(
                [f["penalty_USD_y"].sum() * KUSD for f in frames.values()]
            ),
        }
    )
    return pd.DataFrame(rows).set_index("Heat exchanger")


def table_hydraulic_only(current: Solution, desired: Solution, hydraulic: Solution) -> pd.DataFrame:
    """Table 12 - purely hydraulic approach (Lee et al.) with the budget of Case 1A."""
    cur, des, hyd = _he_frame(current), _he_frame(desired), _he_frame(hydraulic)
    df = pd.DataFrame(
        {
            "Current cooling water flow rate (kg/s)": cur["k_kg_s"],
            "Desired cooling water flow rate (kg/s)": des["k_kg_s"],
            "Optimal cooling water flow rate (kg/s)": hyd["k_kg_s"],
            "Valve head loss (m)": hyd["valve_head_loss_m"],
            "Penalty (kUSD/y)": hyd["penalty_USD_y"] * KUSD,
        }
    )
    df.index.name = "Heat exchanger"
    total = pd.DataFrame(
        {
            "Current cooling water flow rate (kg/s)": [cur["k_kg_s"].sum()],
            "Desired cooling water flow rate (kg/s)": [des["k_kg_s"].sum()],
            "Optimal cooling water flow rate (kg/s)": [hyd["k_kg_s"].sum()],
            "Penalty (kUSD/y)": [hyd["penalty_USD_y"].sum() * KUSD],
        },
        index=["Total"],
    )
    return pd.concat([df, total])


def table_costs(solutions: dict[str, Solution]) -> pd.DataFrame:
    """Cost breakdown (kUSD/y) of several runs side by side (used for Figs. 9-10)."""
    rows = []
    for name, s in solutions.items():
        c = s.costs
        rows.append(
            {
                "Run": name,
                "Pipe (kUSD/y)": c["cpipe"] * KUSD,
                "Pump (kUSD/y)": c["cpump"] * KUSD,
                "Operating (kUSD/y)": c["cope"] * KUSD,
                "Penalty (kUSD/y)": c["cpen"] * KUSD,
                "Objective (kUSD/y)": c["total_cost"] * KUSD,
                "Budget (kUSD/y)": None if c.get("budget") is None else c["budget"] * KUSD,
                "Pump option": "/".join(s.pump_options().values()),
                "Pipes changed": sum(1 for e in s.edges if e["kind"] == "pipe" and e.get("changed"))
                if s.edges
                else 0,
                "Solver status": s.report.get("termination"),
            }
        )
    return pd.DataFrame(rows).set_index("Run")


def flow_deviation(solution: Solution, targets: dict[str, float]) -> float:
    """Sum of squared deviations between cooler flow rates and targets (kg2/s2), Section 3.7."""
    return float(sum((x["k_kg_s"] - targets[x["tag"]]) ** 2 for x in solution.exchangers))
