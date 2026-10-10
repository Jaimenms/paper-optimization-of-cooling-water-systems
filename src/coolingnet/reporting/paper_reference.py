"""Numerical values published in the paper (for side-by-side validation in the notebooks).

Source: J.N.M. Souza, A.L.L. Levy, A.L.H. Costa, Applied Thermal Engineering 128 (2018)
1531-1542, Tables 8-12 and Figs. 9-10. Units as in the paper (kg/s, degC, m, kUSD/y).
"""

from __future__ import annotations

import pandas as pd

HE_TAGS = ["E-101", "E-102", "E-103", "E-104", "E-105"]

TABLE8 = pd.DataFrame(
    {
        "Design condition (C)": [65.00, 80.00, 40.00, 41.00, 41.00],
        "Initial condition (C)": [63.48, 78.39, 39.66, 40.91, 39.75],
        "Current condition (C)": [65.16, 81.59, 41.82, 42.81, 41.53],
        "Current condition penalty (kUSD/y)": [1.96, 19.82, 22.70, 22.61, 6.62],
    },
    index=pd.Index(HE_TAGS, name="Heat exchanger"),
)
TABLE8_TOTAL_PENALTY = 73.71

TABLE9 = pd.DataFrame(
    {
        "Current cooling water flow rate (kg/s)": [11.92, 28.85, 35.57, 15.53, 3.23],
        "Optimal cooling water flow rate (kg/s)": [12.65, 23.04, 33.69, 17.21, 3.58],
        "Valve head loss (m)": [0.49, 3.70, 1.90, 0.00, 0.00],
        "Penalty (kUSD/y)": [0.00, 27.29, 24.86, 16.25, 0.00],
        "Penalty variation (%)": [-100.00, 37.69, 9.52, -28.13, -100.00],
    },
    index=pd.Index(HE_TAGS, name="Heat exchanger"),
)
TABLE9_TOTALS = {"current_flow": 95.10, "optimal_flow": 90.17, "penalty": 68.40, "penalty_variation": -7.20}
NO_BUDGET_TEXT = {"penalty_before": 73.71, "penalty_after": 68.40, "operating_before": 20.16, "operating_after": 20.47, "total_reduction_pct": 5.33}

TABLE10 = pd.DataFrame(
    {
        "Current cooling water flow rate (kg/s)": [11.92, 28.85, 35.57, 15.53, 3.23],
        "Optimal flow Case 1 (kg/s)": [13.56, 30.52, 40.29, 19.96, 3.88],
        "Optimal flow Case 2 (kg/s)": [13.73, 30.26, 41.26, 22.68, 3.94],
        "Valve head loss Case 1 (m)": [0.00, 1.13, 0.00, 0.00, 0.84],
        "Valve head loss Case 2 (m)": [0.11, 0.00, 0.00, 0.00, 1.06],
        "Penalty Case 1 (kUSD/y)": [0.00, 19.67, 18.65, 13.22, 0.00],
        "Penalty Case 2 (kUSD/y)": [0.00, 65.04, 57.91, 27.62, 0.00],
    },
    index=pd.Index(HE_TAGS, name="Heat exchanger"),
)
TABLE10_TOTALS = {"case1": {"flow": 108.21, "penalty": 51.54}, "case2": {"flow": 111.87, "penalty": 150.57}}
UNLIMITED_DESIGNS = {
    "case1": {"pump": "4", "pipes_changed": {"5": 8.0, "6": 8.0}},
    "case2": {"pump": "4", "n_pipes_changed": 10},
}

TABLE11 = pd.DataFrame(
    {
        "Optimal flow 1A (kg/s)": [12.01, 25.71, 35.67, 17.65, 3.66],
        "Optimal flow 1B (kg/s)": [13.51, 30.02, 41.56, 18.12, 3.86],
        "Optimal flow 1C (kg/s)": [13.53, 30.27, 40.96, 18.98, 3.87],
        "Valve head loss 1A (m)": [0.00, 1.45, 0.00, 0.00, 0.03],
        "Valve head loss 1B (m)": [0.51, 1.81, 0.00, 0.00, 1.62],
        "Valve head loss 1C (m)": [0.27, 1.48, 0.00, 0.00, 0.23],
        "Penalty 1A (kUSD/y)": [1.76, 23.79, 22.54, 16.09, 0.00],
        "Penalty 1B (kUSD/y)": [0.00, 20.06, 16.77, 17.37, 0.00],
        "Penalty 1C (kUSD/y)": [0.00, 19.86, 17.65, 15.34, 0.00],
    },
    index=pd.Index(HE_TAGS, name="Heat exchanger"),
)
TABLE11_TOTALS = {"1A": {"flow": 94.70, "penalty": 64.18}, "1B": {"flow": 107.07, "penalty": 54.20}, "1C": {"flow": 107.61, "penalty": 52.85}}
BUDGET_DESIGNS = {
    "1A": {"pump": "1", "pipes_changed": {"5": 8.0, "6": 8.0}},
    "1B": {"pump": "4", "pipes_changed": {}},
    "1C": {"pump": "4", "pipes_changed": {"5": 8.0}},
}

TABLE12 = pd.DataFrame(
    {
        "Current cooling water flow rate (kg/s)": [11.92, 28.85, 35.57, 15.53, 3.23],
        "Desired cooling water flow rate (kg/s)": [11.36, 52.24, 46.22, 21.23, 3.16],
        "Optimal cooling water flow rate (kg/s)": [4.41, 33.03, 39.23, 14.28, 0.073],
        "Valve head loss (m)": [7.14, 0.00, 0.00, 2.58, 6.42],
        "Penalty (kUSD/y)": [36.90, 13.72, 13.51, 24.19, 320.0],
    },
    index=pd.Index(HE_TAGS, name="Heat exchanger"),
)
TABLE12_TOTALS = {"current_flow": 95.10, "desired_flow": 134.21, "optimal_flow": 91.02, "penalty": 408.32}
LEE_FLOW_DEVIATION = {"current_kg2_s2": 696.8, "optimal_kg2_s2": 524.0}
LEE_DESIGN = {"pump": "1", "pipes_changed": {"1": 24.0, "10": 16.0, "15": 18.0}}

# Figs. 9 and 10
FIG9_OBJECTIVE_KUSD = {"No Budget": 88.87, "Case 1A": 86.93, "Case 1B": 85.04, "Case 1C": 84.77, "Case 1": 84.59}
FIG10_PENALTY_REDUCTION_PCT = {"No Budget": 7.21, "Case 1A": 12.95, "Case 1B": 26.48, "Case 1C": 28.30, "Case 1": 30.08}


def compare(paper: pd.DataFrame, computed: pd.DataFrame, columns: dict[str, str] | None = None) -> pd.DataFrame:
    """Interleave paper and computed columns for a quick visual check.

    `columns` maps paper column name -> computed column name (defaults to equal names).
    """
    columns = columns or {c: c for c in paper.columns if c in computed.columns}
    out = {}
    for pc, cc in columns.items():
        out[f"{pc} [paper]"] = paper[pc]
        out[f"{pc} [this work]"] = computed.reindex(paper.index)[cc]
    return pd.DataFrame(out, index=paper.index)
