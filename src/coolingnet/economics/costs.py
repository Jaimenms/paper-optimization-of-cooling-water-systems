"""Cost correlations: pipes (Narang et al.), pumps (Couper et al.), operating cost."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from coolingnet.physics.hydraulics import pump_head

FEET_PER_METRE = 1.0 / 0.3048
INCHES_PER_FOOT = 12.0


def annualization_factor(interest_rate: float, years: int) -> float:
    """r = i (1+i)^ny / ((1+i)^ny - 1) (Eq. 45)."""
    f = (1.0 + interest_rate) ** years
    return interest_rate * f / (f - 1.0)


def pipe_unit_cost(nominal_in: float, c1: float, m: float) -> float:
    """Annualized cost of a pipe of unitary length [USD/(y m)] (Eq. 39): (C1/0.3048)(Dnom/12)^m."""
    return c1 * FEET_PER_METRE * (nominal_in / INCHES_PER_FOOT) ** m


@dataclass(frozen=True)
class PumpCostBreakdown:
    design_head_m: float
    z: float
    f_t: float
    base_cost_usd: float
    annualized_cost_usd_y: float


def pump_capital_cost(
    coefficients: Sequence[float],
    design_flow_m3_s: float,
    f_i: float,
    f_ms: float,
    f_m: float,
    b: Sequence[float],
    annualization: float,
) -> PumpCostBreakdown:
    """Annualized pump capital cost (Eqs. 41-44, Couper et al. 2005)."""
    head = float(pump_head(design_flow_m3_s, coefficients))
    z = 28710.0 * design_flow_m3_s * math.sqrt(head)
    ln_z = math.log(z)
    f_t = math.exp(sum(bj * ln_z**j for j, bj in enumerate(b)))
    base = 1.39 * math.exp(8.833 - 0.6019 * ln_z + 0.0519 * ln_z**2)
    return PumpCostBreakdown(
        design_head_m=head,
        z=z,
        f_t=f_t,
        base_cost_usd=base,
        annualized_cost_usd_y=annualization * f_i * f_ms * f_m * f_t * base,
    )


def pump_operating_cost(
    mass_flow_kg_s,
    head_m,
    gravity: float,
    efficiency: float,
    operating_hours: float,
    energy_cost_usd_kwh: float,
):
    """Operating cost [USD/y] = (m g H / eta) [W] * Nop [h/y] * pc [USD/kWh] / 1000 (Eq. 48)."""
    return (
        mass_flow_kg_s
        * head_m
        * gravity
        / efficiency
        * operating_hours
        * energy_cost_usd_kwh
        / 1000.0
    )
