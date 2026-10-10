"""Structure of the Pyomo MINLP (Section 2 of the paper)."""

from __future__ import annotations

import pyomo.environ as pyo
import pytest

from coolingnet.optimization import Design, ProblemSpec, build_model, selected_design

N_PIPES, N_DIAMETERS, N_PUMPS, N_OPTIONS, N_HE = 17, 20, 1, 4, 5


def _binaries(m, free_only: bool = False) -> list:
    return [
        v
        for v in m.component_data_objects(pyo.Var, active=True, descend_into=True)
        if v.is_binary() and (not v.fixed or not free_only)
    ]


def _has_constraint(m, name: str) -> bool:
    c = getattr(m, name, None)
    return isinstance(c, pyo.Constraint)


@pytest.fixture(scope="module")
def default_model(case):
    return build_model(case, ProblemSpec())


def test_default_model_builds(default_model, network):
    m = default_model
    assert isinstance(m, pyo.ConcreteModel)
    assert m.network is network or len(m.network.edges) == 23
    assert list(m.E) == [e.id for e in network.edges]
    assert len(m.N) == N_DIAMETERS
    assert list(m.S) == ["1", "2", "3", "4"]
    assert list(m.L) == [1, 2, 3, 4, 5]
    assert len(m.M) == 4
    assert len(list(m.component_data_objects(pyo.Objective, active=True))) == 1


def test_default_model_binary_count(default_model):
    # y_pi (17 x 20) + y_pu (1 x 4); the penalty uses the epigraph (no y_he)
    assert len(_binaries(default_model)) == N_PIPES * N_DIAMETERS + N_PUMPS * N_OPTIONS
    assert (
        len(_binaries(default_model, free_only=True)) == N_PIPES * N_DIAMETERS + N_PUMPS * N_OPTIONS
    )
    assert not hasattr(default_model, "y_he")
    assert _has_constraint(default_model, "penalty_epigraph")
    assert not _has_constraint(default_model, "penalty_value")
    assert ProblemSpec().uses_binary_penalty is False


def test_default_model_key_constraints(default_model):
    m = default_model
    for name in (
        "mass_balance",
        "one_diameter",
        "one_pump",
        "zq_lo1",
        "zq_up1",
        "zq_lo2",
        "zq_up2",
        "velocity",
        "circuit_balance",
        "heat_capacity_ratio",
        "water_film",
        "overall_u",
        "effectiveness",
        "hot_outlet",
        "water_outlet",
        "feed_mixing",
        "tower_range",
        "quadrature_temperature",
        "saturated_enthalpy",
        "operating_line",
        "merkel_integral",
        "tower_characteristic",
        "merkel",
        "pipe_cost",
        "pump_cost",
        "operating_cost",
        "penalty_cost",
        "objective_def",
    ):
        assert _has_constraint(m, name), name
    assert not hasattr(m, "budget")
    assert not hasattr(m, "no_downsizing")
    assert len(m.mass_balance) == 18
    assert len(m.circuit_balance) == 5
    assert m.obj.sense == pyo.minimize


def test_flow_deviation_objective_uses_binary_penalty(case):
    spec = ProblemSpec(
        objective="flow_deviation",
        penalty_formulation="binary",
        target_flows_kg_s={tag: 10.0 for tag in case.heat_exchangers},
    )
    assert spec.uses_binary_penalty is True
    m = build_model(case, spec)
    assert hasattr(m, "y_he")
    assert len(_binaries(m)) == N_PIPES * N_DIAMETERS + N_PUMPS * N_OPTIONS + N_HE
    for name in (
        "penalty_value",
        "z_lo1",
        "z_up1",
        "z_lo2",
        "z_up2",
        "penalty_active_lo",
        "penalty_active_up",
    ):
        assert _has_constraint(m, name), name
    assert not _has_constraint(m, "penalty_epigraph")


def test_flow_deviation_requires_targets(case):
    with pytest.raises(ValueError, match="target_flows_kg_s"):
        build_model(case, ProblemSpec(objective="flow_deviation", penalty_formulation="binary"))


def test_explicit_penalty_formulation(case):
    m = build_model(case, ProblemSpec(penalty_formulation="binary"))
    assert hasattr(m, "y_he")
    m2 = build_model(
        case, ProblemSpec(objective="cost_without_penalty", penalty_formulation="epigraph")
    )
    assert not hasattr(m2, "y_he")


def test_design_free_false_fixes_all_design_binaries(case):
    m = build_model(case, ProblemSpec(design_free=False))
    assert all(m.y_pi[i].fixed for i in m.y_pi)
    assert all(m.y_pu[i].fixed for i in m.y_pu)
    assert len(_binaries(m, free_only=True)) == 0
    # the fixed values reproduce the existing design
    assert selected_design(m) == Design.from_case(case)
    assert all(not m.lvalve[l].fixed for l in m.L)  # valves still free by default


def test_valves_free_false_fixes_valves(case):
    m = build_model(case, ProblemSpec(design_free=False, valves_free=False))
    assert all(m.lvalve[l].fixed and pyo.value(m.lvalve[l]) == 0.0 for l in m.L)


def test_thermal_only_model(case):
    m = build_model(
        case, ProblemSpec(hydraulics=False, tower_model="fixed_inlet", fix_hot_outlet_to_spec=True)
    )
    for name in (
        "y_pi",
        "y_pu",
        "zq",
        "v",
        "lvalve",
        "mass_balance",
        "circuit_balance",
        "T_m",
        "IM",
    ):
        assert not hasattr(m, name), name
    assert m.T_w_in.fixed and pyo.value(m.T_w_in) == 32.0
    for h in m.HE:
        assert m.T_hot_out[h].fixed
        assert (
            pyo.value(m.T_hot_out[h]) == case.heat_exchanger(m.he_data[h]["tag"]).hot_outlet_spec_C
        )
    assert m.cpipe.fixed and m.cpump.fixed and m.cope.fixed
    assert len(_binaries(m)) == 0
    # selected_design falls back to the existing design
    assert selected_design(m) == Design.from_case(case)


def test_budget_constraint(case):
    m = build_model(case, ProblemSpec(budget=1000.0))
    assert _has_constraint(m, "budget")
    assert m.budget.upper is not None and pyo.value(m.budget.upper) == pytest.approx(1000.0)
    assert m.budget.lower is None
    assert m.scaling_factor[m.budget] == pytest.approx(1e-4)


def test_no_downsizing_option(case):
    m = build_model(case, ProblemSpec(allow_downsizing=False))
    assert _has_constraint(m, "no_downsizing")
    assert len(m.no_downsizing) == N_PIPES


def test_hot_flow_factor_scales_hot_side_data(case):
    m = build_model(case, ProblemSpec(hot_flow_factor=1.2))
    d = m.he_data[19]
    he = case.heat_exchanger("E-101")
    assert d["C_hot"] == pytest.approx(1.2 * 12.0 * 2200.0)
    assert d["h_hot"] == pytest.approx(658.0 * 1.2**he.hot_film_exponent)
    assert d["pen"] == pytest.approx(12500.0)
    m2 = build_model(case, ProblemSpec(penalty_factor=40000.0))
    assert m2.he_data[19]["pen"] == pytest.approx(40000.0)


def test_selected_design_on_fresh_model_is_existing_design(default_model, case):
    design = selected_design(default_model)
    assert design == Design.from_case(case)
    assert design.pipe_diameters_in[1] == 10.0
    assert design.pump_options[2] == "1"
    assert design.changed_pipes(Design.from_case(case)) == []
    assert design.changed_pumps(Design.from_case(case)) == []


def test_initial_point_sums_to_one_per_pipe(default_model):
    m = default_model
    for p in m.PI:
        assert sum(pyo.value(m.y_pi[p, n]) for n in m.N) == pytest.approx(1.0)
    assert sum(pyo.value(m.y_pu[2, s]) for s in m.S) == pytest.approx(1.0)


def test_scaling_suffix_exists(default_model):
    m = default_model
    assert isinstance(m.scaling_factor, pyo.Suffix)
    assert m.scaling_factor.export_enabled()
    assert m.scaling_factor[m.q[1]] == pytest.approx(10.0)
    assert m.scaling_factor[m.fob] == pytest.approx(1e-4)
    assert m.scaling_factor[m.T_w_in] == pytest.approx(0.02)
    # every unfixed variable has a scaling factor
    for v in m.component_data_objects(pyo.Var, active=True, descend_into=True):
        if not v.fixed and not v.is_binary():
            assert v in m.scaling_factor, v.name


def test_params_and_bounds(default_model, case):
    m = default_model
    assert m.params["annualization_factor"] == pytest.approx(0.13387878, rel=1e-6)
    assert m.params["cpu"]["1"] == pytest.approx(3051.461, abs=0.01)
    assert m.params["cpu"]["4"] == pytest.approx(3417.191, abs=0.01)
    assert m.params["dnom"]["10"] == 10.0
    assert m.params["din"]["10"] == pytest.approx(0.2545)
    q_lb, q_ub = m.q_bounds
    assert q_lb == case.pipes.q_min_m3_s
    assert 0.0 < q_ub < case.pipes.q_max_m3_s  # zero-head point of the pump curves
    assert m.T_w_in.lb == pytest.approx(case.cooling_tower.wet_bulb_C)
    assert m.T_w_feed.ub == pytest.approx(case.cooling_tower.max_feed_temperature_C)
