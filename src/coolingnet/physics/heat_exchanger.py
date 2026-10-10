"""Heat exchanger relations based on the P-NTU method (Eqs. 21-28 of the paper)."""

from __future__ import annotations

from coolingnet.physics.backend import NUMPY_OPS, MathOps


def film_coefficient(h_design: float, flow, flow_design: float, exponent: float):
    """Power-law variation of a film coefficient with the flow rate (Eq. 25)."""
    return h_design * (flow / flow_design) ** exponent


def heat_capacity_ratio(hot_capacity_flow_W_K, water_mass_flow_kg_s, cp_water: float):
    """CR = C_hot / (q_w rho_w Cp_w) (Eq. 21), written with the water mass flow rate."""
    return hot_capacity_flow_W_K / (water_mass_flow_kg_s * cp_water)


def overall_u_denominator(
    h_w, h_hot, d_out: float, d_in: float, k_wall: float, fouling: float, ops: MathOps = NUMPY_OPS
):
    """Bracket of Eq. (24): U * bracket = h_w * h_hot.

    bracket = h_hot (d_out/d_in) + h_w h_hot d_out ln(d_out/d_in) / (2 k_wall) + h_w + h_w h_hot Rf
    """
    log_ratio = ops.log(d_out / d_in)
    return (
        h_hot * (d_out / d_in)
        + h_w * h_hot * d_out * log_ratio / (2.0 * k_wall)
        + h_w
        + h_w * h_hot * fouling
    )


def overall_heat_transfer_coefficient(
    h_w, h_hot, d_out: float, d_in: float, k_wall: float, fouling: float, ops: MathOps = NUMPY_OPS
):
    """Overall heat transfer coefficient referred to the outer area (Eq. 23)."""
    return h_w * h_hot / overall_u_denominator(h_w, h_hot, d_out, d_in, k_wall, fouling, ops)


def effectiveness_shell_and_tube(ntu, cr, ops: MathOps = NUMPY_OPS):
    """Effectiveness of a 1 shell pass / even tube passes exchanger (Eq. 26).

    P = 2 / { 1 + CR + sqrt(1 + CR^2) [1 + exp(-NTU s)] / [1 - exp(-NTU s)] },  s = sqrt(1 + CR^2)
    """
    s = ops.sqrt(1.0 + cr**2)
    e = ops.exp(-ntu * s)
    return 2.0 / (1.0 + cr + s * (1.0 + e) / (1.0 - e))


def effectiveness_residual_terms(ntu, cr, ops: MathOps = NUMPY_OPS):
    """Rearranged form used by the optimization model (GAMS `eq_epsilon`):

        P * [(1 + CR)(1 - e) + s (1 + e)] = 2 (1 - e)

    Returns (lhs_factor, rhs) so that `P * lhs_factor == rhs`.
    """
    s = ops.sqrt(1.0 + cr**2)
    e = ops.exp(-ntu * s)
    return (1.0 + cr) * (1.0 - e) + s * (1.0 + e), 2.0 * (1.0 - e)


def hot_outlet_temperature(t_hot_in: float, t_w_in, effectiveness):
    """Eq. (27): T_hot_in - T_hot_out = P (T_hot_in - T_w_in)."""
    return t_hot_in - effectiveness * (t_hot_in - t_w_in)


def water_outlet_temperature(t_hot_in: float, t_w_in, effectiveness, cr):
    """Eq. (28) combined with Eq. (27): T_w_out = T_w_in + CR P (T_hot_in - T_w_in)."""
    return t_w_in + cr * effectiveness * (t_hot_in - t_w_in)
