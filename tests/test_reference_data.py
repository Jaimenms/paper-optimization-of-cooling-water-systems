"""Reference data in data/reference, the editable paper case and the `eval` comparison."""

from __future__ import annotations

import json

import pytest

from coolingnet import load_case
from coolingnet.config.loader import paper_case_path
from coolingnet.paths import cases_dir, reference_dir, repo_root
from coolingnet.reporting import paper_reference as REF
from coolingnet.reporting.evaluation import TOL, evaluate, write_report

TAGS = ["E-101", "E-102", "E-103", "E-104", "E-105"]


# ------------------------------------------------------------------ published values
def test_published_values_file_matches_the_python_api():
    raw = json.loads(REF.published_values_path().read_text())
    assert REF.published_values_path() == reference_dir() / "published_values.json"
    assert raw["paper"]["doi"] == "10.1016/j.applthermaleng.2017.09.089"
    assert REF.PAPER["volume"] == 128 and REF.PAPER["year"] == 2018
    assert "Applied Thermal Engineering 128 (2018) 1531-1542" in REF.citation()
    assert REF.HE_TAGS == TAGS
    for name in ("TABLE8", "TABLE9", "TABLE10", "TABLE11", "TABLE12"):
        df = getattr(REF, name)
        assert list(df.index) == TAGS and df.index.name == "Heat exchanger"
        assert df.notna().all().all()
    assert REF.TABLE8.loc["E-103", "Current condition (C)"] == 41.82
    assert REF.TABLE8_TOTAL_PENALTY == 73.71
    assert REF.TABLE9_TOTALS["penalty"] == 68.40
    assert REF.NO_BUDGET_TEXT["total_reduction_pct"] == 5.33
    assert REF.TABLE10_TOTALS["case2"]["penalty"] == 150.57
    assert REF.UNLIMITED_DESIGNS["case1"] == {"pump": "4", "pipes_changed": {"5": 8.0, "6": 8.0}}
    assert REF.BUDGET_DESIGNS["1B"] == {"pump": "4", "pipes_changed": {}}
    assert REF.TABLE12.loc["E-105", "Optimal cooling water flow rate (kg/s)"] == 0.073
    assert REF.LEE_FLOW_DEVIATION == {"current_kg2_s2": 696.8, "optimal_kg2_s2": 524.0}
    assert REF.LEE_DESIGN["pipes_changed"] == {"1": 24.0, "10": 16.0, "15": 18.0}
    assert list(REF.FIG9_OBJECTIVE_KUSD) == ["No Budget", "Case 1A", "Case 1B", "Case 1C", "Case 1"]
    assert "caption" not in REF.FIG10_PENALTY_REDUCTION_PCT


def test_compare_interleaves_columns():
    out = REF.compare(REF.TABLE8, REF.TABLE8)
    assert list(out.columns)[:2] == [
        "Design condition (C) [paper]",
        "Design condition (C) [this work]",
    ]
    assert (out["Initial condition (C) [paper]"] == out["Initial condition (C) [this work]"]).all()


# ------------------------------------------------------------------ cases/ and GAMS references
def test_editable_paper_case_equals_the_packaged_default():
    editable = load_case(cases_dir() / "paper_case.yaml")
    assert editable == load_case(paper_case_path())
    assert editable == load_case()


def test_example_case_loads():
    case = load_case(cases_dir() / "example_six_coolers.yaml")
    assert "E-106" in case.heat_exchangers


def test_gams_reference_listings_present():
    files = {p.name for p in reference_dir().glob("d4_*.json")}
    assert files == {
        "d4_part2_actual.json",
        "d4_part2_actual_simulation.json",
        "d4_part2_initial.json",
        "d4_part3.json",
        "d4_part3_quad_dif.json",
        "d4_part4_case01_redo.json",
    }
    part3 = json.loads((reference_dir() / "d4_part3.json").read_text())
    assert part3["817"]["symbols"]["fob"] == pytest.approx(84590.673)
    assert part3["852"]["symbols"]["fob"] == pytest.approx(189783.461)
    assert (repo_root() / "legacy" / "gams" / "coolingnetwork_applied_v21_part0.gms").exists()


# ------------------------------------------------------------------ eval on the committed cache
@pytest.fixture(scope="module")
def evaluation(case):
    return evaluate(case, repo_root() / "results")


def test_eval_covers_every_published_item(evaluation):
    items = evaluation.items()
    for item in (
        "Table 8",
        "Table 9",
        "Table 10 - Case 1",
        "Table 10 - Case 2",
        "Table 11 - Case 1A",
        "Table 11 - Case 1B",
        "Table 11 - Case 1C",
        "Table 12",
        "Fig. 9",
        "Fig. 10",
        "GAMS initial",
        "GAMS case1",
        "GAMS budget_sweep",
    ):
        assert item in items, item
    assert not evaluation.missing, evaluation.missing
    assert evaluation.designs is not None and len(evaluation.designs) == 6


def test_eval_reproduces_tables_8_9_and_case_1(evaluation):
    summary = evaluation.summary()
    for item in (
        "Table 8",
        "Table 9",
        "Table 10 - Case 1",
        "Table 11 - Case 1A",
        "Table 11 - Case 1C",
        "GAMS initial",
        "GAMS current",
        "GAMS case1",
    ):
        assert summary.loc[item, "status"] == "reproduced", (item, summary.loc[item, "status"])
    # documented deviations: local optima of the non-convex MINLP (within 0.03 % of the objective)
    for item in ("Table 10 - Case 2", "Table 11 - Case 1B"):
        devs = [
            d
            for d in evaluation.deviations
            if d.item == item and d.row == "Total" and "Penalty" in d.quantity
        ]
        assert devs and abs(devs[0].deviation_pct) < 0.5
    designs = evaluation.designs
    assert bool(designs.loc["Case 1", "match"]) and bool(designs.loc["Case 1A", "match"])
    # Case 1C: pipes 5 and 6 (same length, diameter and flow) are interchangeable
    assert designs.loc["Case 1C", "pump (this work)"] == "4"
    assert designs.loc["Case 1C", "pipes changed (this work)"] in ("5: 8 in", "6: 8 in")
    # purely hydraulic run: same pump and enlarged pipes as published (+ downsized small pipes)
    hyd = designs.loc["Purely hydraulic (budget 1A)"]
    assert hyd["pump (this work)"] == "1"
    assert all(
        p in hyd["pipes changed (this work)"] for p in ("1: 24 in", "10: 16 in", "15: 18 in")
    )


def test_eval_deviation_records_and_tolerances(evaluation):
    df = evaluation.deviations_frame()
    assert set(df.columns) >= {
        "item",
        "quantity",
        "row",
        "unit",
        "published",
        "this_work",
        "deviation",
        "deviation_pct",
        "within_tolerance",
    }
    assert set(df["unit"]) <= set(TOL)
    t8 = df[(df["item"] == "Table 8") & (df["row"] == "Total")]
    assert len(t8) == 1 and abs(float(t8["deviation"].iloc[0])) < 0.011


def test_write_report_files(evaluation, tmp_path):
    written = write_report(evaluation, tmp_path / "eval")
    names = {p.name for p in written}
    assert {
        "report.md",
        "summary.csv",
        "deviations.csv",
        "designs.csv",
        "table08.csv",
        "table12.csv",
        "figures09_10.csv",
        "gams_listings.csv",
    } <= names
    report = (tmp_path / "eval" / "report.md").read_text()
    assert "## Summary" in report and "| Table 8" in report
