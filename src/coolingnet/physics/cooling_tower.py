"""Counter-current wet cooling tower, Merkel method (Eqs. 32-37 of the paper)."""

from __future__ import annotations

from collections.abc import Sequence

from coolingnet.config.schema import SaturationEnthalpyFit
from coolingnet.physics.backend import NUMPY_OPS, MathOps


def saturated_air_enthalpy(t_water, fit: SaturationEnthalpyFit, ops: MathOps = NUMPY_OPS):
    """Hsat(T) [J/kg] = (a + b T + c exp(d T)) 1e3 (Eq. 36, Serna-Gonzalez et al. 2010)."""
    return (fit.a + fit.b * t_water + fit.c * ops.exp(fit.d * t_water)) * 1.0e3


def quadrature_temperature(t_base, t_feed, alpha: float):
    """Water temperature at a quadrature point: T_m = T_base + (T_feed - T_base) alpha_m (Eq. 35)."""
    return t_base + (t_feed - t_base) * alpha


def air_enthalpy_operating_line(
    t_m, t_base, water_mass_flow_kg_s, air_flow_kg_s: float, h_atm: float, cp_water: float
):
    """Air enthalpy from the tower energy balance (Eq. 34): H_m = Hatm + Cp_w m_w (T_m - T_base) / m_air."""
    return h_atm + cp_water * water_mass_flow_kg_s * (t_m - t_base) / air_flow_kg_s


def merkel_integral(
    t_feed,
    t_base,
    water_mass_flow_kg_s,
    air_flow_kg_s: float,
    h_atm: float,
    cp_water: float,
    fit: SaturationEnthalpyFit,
    points: Sequence[float],
    regularization: float = 1.0,
    ops: MathOps = NUMPY_OPS,
):
    """Merkel integral by quadrature (Eq. 33): IM = Cp_w (T_feed - T_base)/N sum_m 1/(Hsat_m - H_m + eps)."""
    total = 0
    for alpha in points:
        t_m = quadrature_temperature(t_base, t_feed, alpha)
        h_sat = saturated_air_enthalpy(t_m, fit, ops)
        h_m = air_enthalpy_operating_line(
            t_m, t_base, water_mass_flow_kg_s, air_flow_kg_s, h_atm, cp_water
        )
        total = total + 1.0 / (h_sat - h_m + regularization)
    return cp_water * (t_feed - t_base) / len(points) * total


def tower_characteristic(water_to_air_ratio, packing_height_m: float, c_un: float, n: float):
    """Tower characteristic IP = Δpack C_un (m_w / m_air)^(-n) (Eq. 37)."""
    return packing_height_m * c_un * water_to_air_ratio ** (-n)
