"""Reproduction of the paper's result tables with the full MINLP (Bonmin through CasADi).

These tests solve the optimization problems of Sections 3.2-3.4 and are slow
(the unlimited budget case may take several minutes). Deselect with -m "not slow".
"""

from __future__ import annotations

import time

import pytest

from coolingnet.optimization import Design, SolverSettings
from coolingnet.optimization.problems import optimize_debottlenecking, simulate_existing_network

pytestmark = pytest.mark.slow

TABLE_8_INITIAL_T_OUT = [63.48, 78.39, 39.66, 40.91, 39.75]
TABLE_8_INITIAL_FLOWS = [11.92, 28.85, 35.57, 15.53, 3.23]

TABLE_9_FLOWS = [12.65, 23.04, 33.69, 17.21, 3.58]
TABLE_9_VALVES = [0.49, 3.70, 1.90, 0.00, 0.00]
TABLE_9_PENALTY = 68400.0
TABLE_9_TOTAL_COST = 88870.0

TABLE_10_CASE1_FOB = 84590.7
TABLE_10_CASE1_FLOWS = [13.56, 30.52, 40.29, 19.96, 3.88]


def _settings(time_limit_s: float) -> SolverSettings:
    return SolverSettings(name="nlpbb", time_limit_s=time_limit_s)


def _check_internal_consistency(sol):
    c = sol.costs
    assert c["total_cost"] == pytest.approx(
        c["cpipe"] + c["cpump"] + c["cope"] + c["cpen"], rel=1e-9
    )
    assert c["fob"] == pytest.approx(c["total_cost"], rel=1e-6, abs=1e-3)
    df = sol.exchangers_df()
    # cpen and sum(che) are both ~1e-7 when no cooler is penalized: compare in USD/y, not relative
    assert c["cpen"] == pytest.approx(df["penalty_USD_y"].sum(), rel=1e-6, abs=1e-3)
    assert sol.report["termination"] in ("optimal", "feasible")
    assert sol.ok


def test_simulate_existing_network_matches_table_8(case, tags):
    t0 = time.perf_counter()
    sol = simulate_existing_network(case, 1.0, settings=_settings(120))
    elapsed = time.perf_counter() - t0
    assert elapsed < 30.0, f"simulation took {elapsed:.1f} s"
    _check_internal_consistency(sol)
    df = sol.exchangers_df()
    assert df.loc[tags, "T_hot_out_C"].tolist() == pytest.approx(TABLE_8_INITIAL_T_OUT, abs=0.01)
    assert df.loc[tags, "k_kg_s"].tolist() == pytest.approx(TABLE_8_INITIAL_FLOWS, abs=0.01)
    assert df.loc[tags, "valve_head_loss_m"].tolist() == pytest.approx([0.0] * 5, abs=1e-9)
    assert df.loc[tags, "penalty_USD_y"].tolist() == pytest.approx([0.0] * 5, abs=1e-3)
    assert sol.tower["T_w_in_C"] == pytest.approx(32.20, abs=0.01)
    assert sol.costs["cope"] == pytest.approx(20160.0, abs=1.0)
    assert sol.costs["cpipe"] == pytest.approx(0.0, abs=1e-3)
    assert sol.costs["cpump"] == pytest.approx(0.0, abs=1e-3)
    existing = Design.from_case(case)
    assert sol.pipe_diameters() == {str(k): v for k, v in existing.pipe_diameters_in.items()}
    assert sol.pump_options() == {"2": "1"}
    assert sol.label == "simulation_x1"


def test_no_budget_matches_table_9(case, tags):
    t0 = time.perf_counter()
    sol = optimize_debottlenecking(case, budget=0.0, settings=_settings(120))
    elapsed = time.perf_counter() - t0
    _check_internal_consistency(sol)
    assert sol.label == "no_budget"
    df = sol.exchangers_df()
    assert df.loc[tags, "k_kg_s"].tolist() == pytest.approx(TABLE_9_FLOWS, abs=0.02)
    assert df.loc[tags, "valve_head_loss_m"].tolist() == pytest.approx(TABLE_9_VALVES, abs=0.02)
    assert sol.costs["cpen"] == pytest.approx(TABLE_9_PENALTY, abs=100.0)
    assert sol.costs["total_cost"] == pytest.approx(TABLE_9_TOTAL_COST, abs=100.0)
    # no budget: the design cannot change
    assert sol.costs["cpipe"] == pytest.approx(0.0, abs=1e-3)
    assert sol.costs["cpump"] == pytest.approx(0.0, abs=1e-3)
    existing = Design.from_case(case)
    assert sol.pipe_diameters() == {str(k): v for k, v in existing.pipe_diameters_in.items()}
    assert sol.pump_options() == {"2": "1"}
    # E-101 and E-105 are brought back to their set-points; the others are penalized
    assert df.loc["E-101", "penalty_USD_y"] == pytest.approx(0.0, abs=1.0)
    assert df.loc["E-105", "penalty_USD_y"] == pytest.approx(0.0, abs=1.0)
    assert (df.loc[["E-102", "E-103", "E-104"], "penalty_USD_y"] > 1000.0).all()
    assert elapsed < 120.0


def test_unlimited_budget_case_1_matches_table_10(case, tags):
    t0 = time.perf_counter()
    sol = optimize_debottlenecking(case, budget=None, settings=_settings(600))
    elapsed = time.perf_counter() - t0
    assert elapsed < 600.0 + 60.0, f"optimization took {elapsed:.1f} s"
    _check_internal_consistency(sol)
    assert sol.label == "unlimited_budget"
    assert sol.costs["fob"] == pytest.approx(TABLE_10_CASE1_FOB, abs=50.0)
    df = sol.exchangers_df()
    assert df.loc[tags, "k_kg_s"].tolist() == pytest.approx(TABLE_10_CASE1_FLOWS, abs=0.05)
    # interventions: pipes 5 and 6 (6 in -> 8 in) and the largest pump
    existing = Design.from_case(case)
    diameters = sol.pipe_diameters()
    changed = sorted(
        int(k) for k, v in diameters.items() if abs(v - existing.pipe_diameters_in[int(k)]) > 1e-9
    )
    assert changed == [5, 6]
    assert diameters["5"] == 8.0 and diameters["6"] == 8.0
    assert sol.pump_options() == {"2": "4"}
    assert sol.costs["cpump"] == pytest.approx(3417.19, abs=0.01)
    assert sol.costs["cpipe"] > 0.0
    assert sol.costs["cpen"] < TABLE_9_PENALTY
