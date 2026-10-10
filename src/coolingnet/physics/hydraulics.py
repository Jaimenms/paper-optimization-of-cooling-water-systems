"""Hydraulic relations: Hazen-Williams, pump curves, cooler head loss, velocity (Eqs. 4, 9, 19, 31)."""

from __future__ import annotations

import math
from collections.abc import Sequence

HAZEN_WILLIAMS_FLOW_EXPONENT = 1.852
HAZEN_WILLIAMS_DIAMETER_EXPONENT = 4.8704
HAZEN_WILLIAMS_C_EXPONENT = 1.85  # as in Eq. (4) of the paper


def hazen_williams_coefficient(c: float) -> float:
    """Multiplier 10.67 / c^1.85 of the Hazen-Williams equation (SI units)."""
    return 10.67 / c**HAZEN_WILLIAMS_C_EXPONENT


def hazen_williams_head_loss(q, inner_diameter_m: float, length_m: float, c: float):
    """Head loss [m] of a pipe section of length L for a volumetric flow q [m3/s] (Eq. 4)."""
    return (
        hazen_williams_coefficient(c)
        * q**HAZEN_WILLIAMS_FLOW_EXPONENT
        / inner_diameter_m**HAZEN_WILLIAMS_DIAMETER_EXPONENT
        * length_m
    )


def diameter_resistance(inner_diameter_m: float) -> float:
    """1 / D^4.8704, the diameter dependent factor of Eq. (8)."""
    return 1.0 / inner_diameter_m**HAZEN_WILLIAMS_DIAMETER_EXPONENT


def pump_head(q, coefficients: Sequence[float]):
    """Pump curve head [m] = sum_i a_i q^i (Eq. 19)."""
    head = 0
    for i, a in enumerate(coefficients):
        head = head + a * q**i if i > 0 else head + a
    return head


def heat_exchanger_head_loss(flow, flow_design: float, head_loss_design_m: float, exponent: float):
    """Power-law head loss of a cooler (Eq. 31); `flow` may be mass or volumetric (ratio)."""
    return head_loss_design_m * (flow / flow_design) ** exponent


def velocity(q, inner_diameter_m: float):
    """Mean velocity [m/s] in a circular pipe."""
    return 4.0 * q / (math.pi * inner_diameter_m**2)


def velocity_factor(inner_diameter_m: float) -> float:
    """4 / (pi D^2): velocity per unit volumetric flow rate."""
    return 4.0 / (math.pi * inner_diameter_m**2)
