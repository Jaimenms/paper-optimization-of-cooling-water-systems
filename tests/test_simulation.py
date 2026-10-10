"""NumPy/SciPy simulation of the existing design (Table 8 of the paper)."""

from __future__ import annotations

import pytest

from coolingnet.simulation import SimulationResult, simulate_design

TABLE_8_INITIAL = [63.48, 78.39, 39.66, 40.91, 39.75]
TABLE_8_CURRENT = [65.16, 81.59, 41.82, 42.81, 41.53]
INITIAL_FLOWS = [11.92, 28.85, 35.57, 15.53, 3.23]


@pytest.fixture(scope="module")
def initial(case):
    return simulate_design(case, hot_flow_factor=1.0)


@pytest.fixture(scope="module")
def current(case):
    return simulate_design(case, hot_flow_factor=1.2)


def test_initial_condition_matches_table_8(initial, tags):
    assert isinstance(initial, SimulationResult)
    assert initial.converged is True
    t_out = [initial.exchangers[t]["T_hot_out_C"] for t in tags]
    assert t_out == pytest.approx(TABLE_8_INITIAL, abs=0.01)
    assert initial.T_w_in_C == pytest.approx(32.20, abs=0.01)
    assert initial.operating_cost_USD_y == pytest.approx(20160, abs=1)
    assert initial.penalty_USD_y == pytest.approx(0.0, abs=1e-9)
    assert initial.total_cost_USD_y == pytest.approx(initial.operating_cost_USD_y)


def test_initial_condition_water_flows(initial, tags):
    flows = [initial.exchangers[t]["k_kg_s"] for t in tags]
    assert flows == pytest.approx(INITIAL_FLOWS, abs=0.01)
    # mass balance: the pump carries the sum of the circuit flows
    rho = 995.0
    assert initial.edge_flows_m3_s[2] * rho == pytest.approx(sum(flows), rel=1e-9)
    assert initial.details["hydraulic_residual"] < 1e-8


def test_initial_condition_consistency(initial, tags):
    for t in tags:
        x = initial.exchangers[t]
        assert x["T_w_in_C"] == pytest.approx(initial.T_w_in_C)
        assert x["T_w_out_C"] > x["T_w_in_C"]
        assert 0.0 < x["effectiveness"] < 1.0
        assert x["valve_head_loss_m"] == 0.0
    assert initial.T_w_feed_C > initial.T_w_in_C
    assert initial.T_w_feed_C < 45.0  # Eq. (30)
    assert set(initial.valve_head_losses_m) == {1, 2, 3, 4, 5}
    assert all(v == 0.0 for v in initial.valve_head_losses_m.values())


def test_current_condition_matches_table_8(current, tags):
    assert current.converged is True
    t_out = [current.exchangers[t]["T_hot_out_C"] for t in tags]
    assert t_out == pytest.approx(TABLE_8_CURRENT, abs=0.01)
    assert current.penalty_USD_y == pytest.approx(73710, abs=5)
    assert all(
        current.exchangers[t]["T_hot_out_C"] > current.exchangers[t]["T_hot_out_spec_C"]
        for t in tags
    )


def test_current_and_initial_share_hydraulics(initial, current, tags):
    for t in tags:
        assert current.exchangers[t]["k_kg_s"] == pytest.approx(
            initial.exchangers[t]["k_kg_s"], rel=1e-9
        )
    assert current.operating_cost_USD_y == pytest.approx(initial.operating_cost_USD_y, rel=1e-9)
    assert current.T_w_in_C > initial.T_w_in_C


def test_penalty_breakdown(current, tags):
    pens = {t: current.exchangers[t]["penalty_USD_y"] for t in tags}
    for t in tags:
        x = current.exchangers[t]
        assert pens[t] == pytest.approx(
            12500.0 * max(0.0, x["T_hot_out_C"] - x["T_hot_out_spec_C"])
        )
    assert sum(pens.values()) == pytest.approx(current.penalty_USD_y)


def test_penalty_factor_override(case, current, tags):
    scaled = simulate_design(case, hot_flow_factor=1.2, penalty_factor=25000.0)
    assert scaled.penalty_USD_y == pytest.approx(2 * current.penalty_USD_y, rel=1e-9)
    per_tag = simulate_design(case, hot_flow_factor=1.2, penalty_factor={t: 0.0 for t in tags})
    assert per_tag.penalty_USD_y == 0.0


def test_valve_head_loss_reduces_flow(case, initial):
    throttled = simulate_design(case, valve_head_losses_m={2: 3.0})
    assert throttled.converged
    assert throttled.exchangers["E-102"]["k_kg_s"] < initial.exchangers["E-102"]["k_kg_s"]
    assert throttled.exchangers["E-101"]["k_kg_s"] > initial.exchangers["E-101"]["k_kg_s"]
    assert throttled.valve_head_losses_m[2] == 3.0


def test_fixed_inlet_tower_model(case):
    fixed = simulate_design(case, tower_model="fixed_inlet", water_inlet_C=32.0)
    assert fixed.converged
    assert fixed.T_w_in_C == 32.0


def test_quadrature_points_of_the_paper_text_give_a_different_result(case, initial):
    """The paper text states abscissae (0.1, 0.4, 0.6, 0.9); the GAMS code (and the packaged
    case) uses (0.1, 0.4, 0.6, 0.7). Document that the choice changes the tower result."""
    variant = case.with_updates(
        cooling_tower=case.cooling_tower.model_copy(
            update={"quadrature_points": [0.1, 0.4, 0.6, 0.9]}
        )
    )
    assert case.cooling_tower.quadrature_points == [0.1, 0.4, 0.6, 0.7]
    other = simulate_design(variant, hot_flow_factor=1.0)
    assert other.converged
    assert other.T_w_in_C != pytest.approx(initial.T_w_in_C, abs=0.01)
    assert other.T_w_in_C == pytest.approx(32.13, abs=0.01)
