"""Physical and economic correlations checked against the original GAMS listings."""

from __future__ import annotations

import math

import pytest

from coolingnet.config.schema import SaturationEnthalpyFit
from coolingnet.economics import (
    annualization_factor,
    pipe_unit_cost,
    pump_capital_cost,
    pump_operating_cost,
)
from coolingnet.physics import (
    NUMPY_OPS,
    effectiveness_shell_and_tube,
    hazen_williams_head_loss,
    overall_heat_transfer_coefficient,
    pump_head,
    saturated_air_enthalpy,
    tower_characteristic,
    velocity,
)

PUMP_1 = [31.5, -135.0, -415.6]
PUMP_4 = [46.2, -198.0, -609.5]
Q_DESIGN = 0.095276382
COST_B = [5.1029, -1.2217, 0.0771]


@pytest.fixture(scope="module")
def r_ann() -> float:
    return annualization_factor(0.12, 20)


def test_annualization_factor(r_ann):
    assert r_ann == pytest.approx(0.13387878, rel=1e-6)


def test_pump_capital_cost_option_1(r_ann):
    pc = pump_capital_cost(PUMP_1, Q_DESIGN, 2.8, 1.3, 1.35, COST_B, r_ann)
    assert pc.annualized_cost_usd_y == pytest.approx(3051.461, abs=0.01)
    assert pc.design_head_m == pytest.approx(14.865, abs=1e-3)
    assert pc.z == pytest.approx(28710.0 * Q_DESIGN * math.sqrt(pc.design_head_m))
    assert pc.annualized_cost_usd_y == pytest.approx(
        r_ann * 2.8 * 1.3 * 1.35 * pc.f_t * pc.base_cost_usd
    )


def test_pump_capital_cost_option_4(r_ann):
    pc = pump_capital_cost(PUMP_4, Q_DESIGN, 2.8, 1.3, 1.35, COST_B, r_ann)
    assert pc.annualized_cost_usd_y == pytest.approx(3417.191, abs=0.01)


def test_existing_pipes_total_cost(case):
    total = sum(
        pipe_unit_cost(p.diameter_in, 7.0386, 1.4393) * p.length_m for p in case.network.pipes
    )
    assert total == pytest.approx(18617.86, abs=0.1)


def test_pipe_unit_cost_formula():
    # (C1 / 0.3048) (Dnom / 12)^m
    assert pipe_unit_cost(12.0, 7.0386, 1.4393) == pytest.approx(7.0386 / 0.3048)
    assert pipe_unit_cost(6.0, 7.0386, 1.4393) == pytest.approx(7.0386 / 0.3048 * 0.5**1.4393)


def test_pump_head():
    assert pump_head(95.09 / 995, PUMP_1) == pytest.approx(14.803, abs=1e-3)
    assert pump_head(0.0, PUMP_4) == pytest.approx(46.2)


def test_pump_operating_cost():
    # m g H / eta [W] * h/y * USD/kWh / 1000
    assert pump_operating_cost(95.09, 14.803, 9.81, 0.6, 8760.0, 0.10) == pytest.approx(
        95.09 * 14.803 * 9.81 / 0.6 * 8760.0 * 0.10 / 1000.0
    )


def test_hazen_williams_head_loss():
    assert hazen_williams_head_loss(0.095276, 0.2545, 10, 120) == pytest.approx(0.1532, abs=1e-3)
    assert hazen_williams_head_loss(0.095276, 0.3033, 200, 120) == pytest.approx(1.304, abs=1e-3)


def test_velocity():
    assert velocity(0.1, 0.2545) == pytest.approx(4 * 0.1 / (math.pi * 0.2545**2))


def test_effectiveness_limits_and_reference_value():
    # CR -> 0: P -> 1 - exp(-NTU)
    assert effectiveness_shell_and_tube(1.0, 1e-9) == pytest.approx(1.0 - math.exp(-1.0), abs=1e-6)
    assert effectiveness_shell_and_tube(0.481, 0.534) == pytest.approx(0.3452, abs=5e-4)
    # explicit numpy backend gives the same value
    assert effectiveness_shell_and_tube(0.481, 0.534, NUMPY_OPS) == pytest.approx(0.3452, abs=5e-4)
    # monotonic in NTU, bounded by 1
    p_small, p_big = effectiveness_shell_and_tube(0.5, 0.5), effectiveness_shell_and_tube(5.0, 0.5)
    assert 0.0 < p_small < p_big < 1.0


def test_overall_heat_transfer_coefficient():
    u = overall_heat_transfer_coefficient(10615, 658, 0.0207, 0.01905, 50, 5.1e-4)
    assert u == pytest.approx(465.3, abs=0.5)
    # U is lower than both film coefficients
    assert u < 658


def test_saturated_air_enthalpy_at_30_c():
    fit = SaturationEnthalpyFit(a=-6.38887667, b=0.86581791, c=15.7153617, d=0.05439778)
    h = saturated_air_enthalpy(30.0, fit)
    assert 95e3 < h < 105e3
    # increasing with temperature
    assert saturated_air_enthalpy(40.0, fit) > h


def test_tower_characteristic():
    assert tower_characteristic(1.5, 2.0, 0.54, 0.66) == pytest.approx(2 * 0.54 * 1.5**-0.66)
