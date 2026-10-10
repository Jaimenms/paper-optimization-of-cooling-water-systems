"""Numerical values published in the paper (side-by-side validation in the notebooks and `eval`).

Source: J.N.M. Souza, A.L.L. Levy, A.L.H. Costa, Applied Thermal Engineering 128 (2018)
1531-1542, Tables 8-12, Figs. 9-10 and the text of Sections 3.3-3.7. The numbers live in
``data/reference/published_values.json`` (units as printed: kg/s, degC, m, kUSD/y); this module
loads them once and exposes them as pandas frames and dictionaries.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from coolingnet.paths import reference_dir


def published_values_path() -> Path:
    return reference_dir() / "published_values.json"


@lru_cache(maxsize=1)
def load_published_values() -> dict:
    """The raw content of ``data/reference/published_values.json``."""
    return json.loads(published_values_path().read_text(encoding="utf-8"))


_PV = load_published_values()

PAPER: dict = _PV["paper"]
"""Bibliographic reference of the paper (authors, title, journal, volume, pages, year, doi)."""

HE_TAGS: list[str] = list(_PV["heat_exchangers"])


def _frame(key: str) -> pd.DataFrame:
    return pd.DataFrame(_PV[key]["columns"], index=pd.Index(HE_TAGS, name="Heat exchanger"))


def _no_caption(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "caption"}


TABLE8 = _frame("table8")
TABLE8_TOTAL_PENALTY: float = _PV["table8"]["totals"]["Current condition penalty (kUSD/y)"]

TABLE9 = _frame("table9")
TABLE9_TOTALS: dict = _PV["table9"]["totals"]
NO_BUDGET_TEXT: dict = _no_caption(_PV["table9"]["text"])

TABLE10 = _frame("table10")
TABLE10_TOTALS: dict = _PV["table10"]["totals"]
UNLIMITED_DESIGNS: dict = _no_caption(_PV["table10"]["designs"])

TABLE11 = _frame("table11")
TABLE11_TOTALS: dict = _PV["table11"]["totals"]
BUDGET_DESIGNS: dict = _no_caption(_PV["table11"]["designs"])

TABLE12 = _frame("table12")
TABLE12_TOTALS: dict = _PV["table12"]["totals"]
LEE_FLOW_DEVIATION: dict = _no_caption(_PV["table12"]["flow_deviation_kg2_s2"])
LEE_DESIGN: dict = _no_caption(_PV["table12"]["design"])

# Figs. 9 and 10
FIG9_OBJECTIVE_KUSD: dict = _no_caption(_PV["figures"]["fig9_objective_kUSD_y"])
FIG10_PENALTY_REDUCTION_PCT: dict = _no_caption(_PV["figures"]["fig10_penalty_reduction_pct"])


def citation() -> str:
    """One-line citation of the paper."""
    p = PAPER
    return (
        f"{p['authors']}, {p['title']}, {p['journal']} {p['volume']} ({p['year']}) "
        f"{p['pages']}. https://doi.org/{p['doi']}"
    )


def compare(
    paper: pd.DataFrame, computed: pd.DataFrame, columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """Interleave paper and computed columns for a quick visual check.

    `columns` maps paper column name -> computed column name (defaults to equal names).
    """
    columns = columns or {c: c for c in paper.columns if c in computed.columns}
    out = {}
    for pc, cc in columns.items():
        out[f"{pc} [paper]"] = paper[pc]
        out[f"{pc} [this work]"] = computed.reindex(paper.index)[cc]
    return pd.DataFrame(out, index=paper.index)


__all__ = [
    "BUDGET_DESIGNS",
    "FIG9_OBJECTIVE_KUSD",
    "FIG10_PENALTY_REDUCTION_PCT",
    "HE_TAGS",
    "LEE_DESIGN",
    "LEE_FLOW_DEVIATION",
    "NO_BUDGET_TEXT",
    "PAPER",
    "TABLE8",
    "TABLE8_TOTAL_PENALTY",
    "TABLE9",
    "TABLE9_TOTALS",
    "TABLE10",
    "TABLE10_TOTALS",
    "TABLE11",
    "TABLE11_TOTALS",
    "TABLE12",
    "TABLE12_TOTALS",
    "UNLIMITED_DESIGNS",
    "citation",
    "compare",
    "load_published_values",
    "published_values_path",
]
