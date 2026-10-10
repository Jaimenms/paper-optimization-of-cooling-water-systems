"""Simulate a given network design: hydraulic balance, coolers and tower (no optimization).

This is a deliberately independent implementation (NumPy + SciPy root finding)
used to cross-check the Pyomo/SCIP model and to evaluate scenarios quickly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq, root

from coolingnet.config.schema import CaseStudy
from coolingnet.economics.costs import pump_operating_cost
from coolingnet.network.graph import Network, build_network
from coolingnet.optimization.spec import Design
from coolingnet.physics.cooling_tower import merkel_integral, tower_characteristic
from coolingnet.physics.heat_exchanger import (
    effectiveness_shell_and_tube,
    film_coefficient,
    heat_capacity_ratio,
    hot_outlet_temperature,
    overall_heat_transfer_coefficient,
    water_outlet_temperature,
)
from coolingnet.physics.hydraulics import (
    hazen_williams_head_loss,
    heat_exchanger_head_loss,
    pump_head,
    velocity,
)


@dataclass
class SimulationResult:
    circuit_flows_m3_s: dict[int, float]
    edge_flows_m3_s: dict
    valve_head_losses_m: dict[int, float]
    pump_heads_m: dict
    T_w_in_C: float
    T_w_feed_C: float
    exchangers: dict[str, dict]
    operating_cost_USD_y: float
    penalty_USD_y: float
    converged: bool
    details: dict = field(default_factory=dict)

    @property
    def total_cost_USD_y(self) -> float:
        return self.operating_cost_USD_y + self.penalty_USD_y


def _hydraulic_residuals(q_circ, net: Network, case: CaseStudy, design: Design, valves: dict[int, float], hes):
    lam = net.circuit_matrix
    q_edge = lam.T @ q_circ  # Eq. (1)-(2) satisfied by construction
    rho = case.water.density_kg_m3
    pipes = case.pipes
    res = np.zeros(len(net.circuits))
    for c in net.circuits:
        total = -net.elevation_difference_m - valves.get(c.index, 0.0)
        for eid in c.edge_ids:
            e = net.edge(eid)
            qk = q_edge[net.edge_index(eid)]
            if e.kind == "pump":
                total += pump_head(qk, case.pumps.options[design.pump_options[eid]].coefficients)
            elif e.kind == "pipe":
                dia = pipes.by_nominal(design.pipe_diameters_in[eid]).inner_m
                total -= hazen_williams_head_loss(abs(qk), dia, e.length_m, pipes.hazen_williams_c) * np.sign(qk)
            else:
                h = hes[eid]
                total -= heat_exchanger_head_loss(rho * qk, h.water_flow_design_kg_s, h.head_loss_design_m, h.head_loss_exponent)
        res[c.index - 1] = total
    return res, q_edge


def min_driving_force(t_base: float, t_feed: float, k_tot: float, tower, cp_w: float) -> float:
    """Smallest Hsat - H over the quadrature points (must be positive for a physical tower)."""
    from coolingnet.physics.cooling_tower import air_enthalpy_operating_line, quadrature_temperature, saturated_air_enthalpy

    worst = np.inf
    for alpha in tower.quadrature_points:
        t_m = quadrature_temperature(t_base, t_feed, alpha)
        worst = min(worst, saturated_air_enthalpy(t_m, tower.saturation_enthalpy) - air_enthalpy_operating_line(t_m, t_base, k_tot, tower.air_flow_kg_s, tower.atmospheric_air_enthalpy_J_kg, cp_w))
    return float(worst)


def _physical_merkel_root(residual, thermal_state, tower, k_tot: float, cp_w: float, n_grid: int = 200) -> tuple[float, bool]:
    """Basin temperature solving IM = IP with a positive enthalpy driving force everywhere.

    The regularized Merkel integral may have spurious roots where the operating line crosses
    the saturation curve (negative driving force). Scanning from the warm end, the first sign
    change with positive driving forces is the physical solution.
    """
    lo, hi = tower.wet_bulb_C + 1e-6, tower.max_feed_temperature_C
    grid = np.linspace(hi, lo, n_grid)
    prev_t, prev_r = grid[0], residual(grid[0])
    for t in grid[1:]:
        r = residual(t)
        if np.isfinite(prev_r) and np.isfinite(r) and prev_r * r < 0:
            root = brentq(residual, t, prev_t, xtol=1e-10)
            _, t_feed = thermal_state(root)
            if min_driving_force(root, t_feed, k_tot, tower, cp_w) >= tower.min_enthalpy_driving_force_J_kg:
                return float(root), True
        prev_t, prev_r = t, r
    return lo, False


def simulate_design(
    case: CaseStudy,
    design: Design | None = None,
    valve_head_losses_m: dict[int, float] | None = None,
    hot_flow_factor: float = 1.0,
    tower_model: str = "merkel",
    water_inlet_C: float | None = None,
    network: Network | None = None,
    penalty_factor: float | dict[str, float] | None = None,
) -> SimulationResult:
    """Solve the hydraulic + thermal equations of a fixed design.

    Parameters
    ----------
    design: pipe diameters and pump option (defaults to the existing network).
    valve_head_losses_m: head loss inserted in each circuit (index -> m), default fully open.
    hot_flow_factor: multiplier of the design hot stream flow rates.
    tower_model: "merkel" (cooling tower equations) or "fixed_inlet" (water_inlet_C given).
    """
    net = network or build_network(case.network)
    design = design or Design.from_case(case)
    valves = valve_head_losses_m or {}
    hes = {h.edge_id: h for h in case.resolved_heat_exchangers}
    rho, cp_w = case.water.density_kg_m3, case.water.cp_J_kgK

    # ---------------------------------------------------------- hydraulics
    q0 = np.array([hes[c.he_edge].water_flow_design_kg_s / rho for c in net.circuits])
    sol = root(lambda x: _hydraulic_residuals(np.abs(x), net, case, design, valves, hes)[0], q0, method="hybr", tol=1e-12)
    q_circ = np.abs(sol.x)
    _, q_edge = _hydraulic_residuals(q_circ, net, case, design, valves, hes)
    hyd_ok = sol.success and np.max(np.abs(sol.fun)) < 1e-8

    # ---------------------------------------------------------- thermal
    he_ids = [h.id for h in net.heat_exchangers]
    k_w = {h: rho * q_edge[net.edge_index(h)] for h in he_ids}
    k_tot = sum(k_w.values())

    def thermal_state(t_w_in: float):
        out = {}
        for h in he_ids:
            d = hes[h]
            k_hot = hot_flow_factor * d.hot_flow_design_kg_s
            c_hot = k_hot * d.cp_hot_J_kgK
            h_w = film_coefficient(d.h_water_design_W_m2K, k_w[h], d.water_flow_design_kg_s, d.water_film_exponent)
            h_hot = film_coefficient(d.h_hot_design_W_m2K, k_hot, d.hot_flow_design_kg_s, d.hot_film_exponent)
            u = overall_heat_transfer_coefficient(h_w, h_hot, d.tube_outer_diameter_m, d.tube_inner_diameter_m, d.wall_conductivity_W_mK, d.fouling_m2K_W)
            ntu = u * d.area_m2 / c_hot
            cr = heat_capacity_ratio(c_hot, k_w[h], cp_w)
            p = effectiveness_shell_and_tube(ntu, cr)
            t_hot_out = hot_outlet_temperature(d.hot_inlet_C, t_w_in, p)
            t_w_out = water_outlet_temperature(d.hot_inlet_C, t_w_in, p, cr)
            out[h] = {"h_w": h_w, "h_hot": h_hot, "U": u, "NTU": ntu, "CR": cr, "P": p, "T_hot_out": t_hot_out, "T_w_out": t_w_out, "C_hot": c_hot, "k_hot": k_hot}
        t_feed = sum(k_w[h] * out[h]["T_w_out"] for h in he_ids) / k_tot
        return out, t_feed

    tower = case.cooling_tower
    if tower_model == "fixed_inlet":
        t_w_in = water_inlet_C if water_inlet_C is not None else hes[he_ids[0]].water_inlet_design_C
        states, t_feed = thermal_state(t_w_in)
        thermal_ok = True
    else:

        def merkel_residual(t_w_in: float) -> float:
            _, t_feed = thermal_state(t_w_in)
            im = merkel_integral(t_feed, t_w_in, k_tot, tower.air_flow_kg_s, tower.atmospheric_air_enthalpy_J_kg, cp_w, tower.saturation_enthalpy, tower.quadrature_points, tower.merkel_regularization_J_kg)
            ip = tower_characteristic(k_tot / tower.air_flow_kg_s, tower.packing_height_m, tower.C_un, tower.n)
            return im - ip

        t_w_in, thermal_ok = _physical_merkel_root(merkel_residual, thermal_state, tower, k_tot, cp_w)
        states, t_feed = thermal_state(t_w_in)

    # ---------------------------------------------------------- economics
    econ = case.economics
    pump_heads = {}
    cope = 0.0
    for u in net.pumps:
        qk = q_edge[net.edge_index(u.id)]
        head = float(pump_head(qk, case.pumps.options[design.pump_options[u.id]].coefficients))
        pump_heads[u.id] = head
        cope += float(pump_operating_cost(rho * qk, head, econ.gravity_m_s2, case.pumps.efficiency, econ.operating_hours_per_year, econ.energy_cost_USD_kWh))

    exchangers = {}
    cpen = 0.0
    for h in he_ids:
        d = hes[h]
        pen = d.penalty_factor_USD_per_C_y if penalty_factor is None else (penalty_factor[d.tag] if isinstance(penalty_factor, dict) else penalty_factor)
        s = states[h]
        che = pen * max(0.0, s["T_hot_out"] - d.hot_outlet_spec_C)
        cpen += che
        c = net.circuit_of(h)
        exchangers[d.tag] = {
            "edge_id": h,
            "circuit": c.index,
            "k_kg_s": k_w[h],
            "T_hot_out_C": s["T_hot_out"],
            "T_hot_out_spec_C": d.hot_outlet_spec_C,
            "T_w_in_C": t_w_in,
            "T_w_out_C": s["T_w_out"],
            "effectiveness": s["P"],
            "NTU": s["NTU"],
            "CR": s["CR"],
            "U_W_m2K": s["U"],
            "duty_W": s["C_hot"] * (d.hot_inlet_C - s["T_hot_out"]),
            "penalty_USD_y": che,
            "valve_head_loss_m": valves.get(c.index, 0.0),
            "head_loss_m": float(heat_exchanger_head_loss(k_w[h], d.water_flow_design_kg_s, d.head_loss_design_m, d.head_loss_exponent)),
        }

    velocities = {}
    for p in net.pipes:
        dia = case.pipes.by_nominal(design.pipe_diameters_in[p.id]).inner_m
        velocities[p.id] = float(velocity(q_edge[net.edge_index(p.id)], dia))

    return SimulationResult(
        circuit_flows_m3_s={c.index: float(q_circ[c.index - 1]) for c in net.circuits},
        edge_flows_m3_s={e.id: float(q_edge[net.edge_index(e.id)]) for e in net.edges},
        valve_head_losses_m={c.index: valves.get(c.index, 0.0) for c in net.circuits},
        pump_heads_m=pump_heads,
        T_w_in_C=float(t_w_in),
        T_w_feed_C=float(t_feed),
        exchangers=exchangers,
        operating_cost_USD_y=cope,
        penalty_USD_y=cpen,
        converged=bool(hyd_ok and thermal_ok),
        details={"velocities_m_s": velocities, "hydraulic_residual": float(np.max(np.abs(sol.fun)))},
    )
