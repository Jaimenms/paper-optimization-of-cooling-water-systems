"""Pyomo formulation of the hydraulic debottlenecking MINLP (Section 2 of the paper).

Equation numbers in the comments refer to Souza, Levy & Costa (2018). The model is
built from a `CaseStudy` (data) and a `ProblemSpec` (which variant to build).
"""

from __future__ import annotations

import math

import numpy as np
import pyomo.environ as pyo

from coolingnet.config.schema import CaseStudy
from coolingnet.economics.costs import annualization_factor, pipe_unit_cost, pump_capital_cost
from coolingnet.network.graph import Network, build_network
from coolingnet.optimization.spec import Design, ProblemSpec
from coolingnet.physics import PYOMO_OPS
from coolingnet.physics.cooling_tower import (
    air_enthalpy_operating_line,
    quadrature_temperature,
    saturated_air_enthalpy,
)
from coolingnet.physics.heat_exchanger import effectiveness_residual_terms, overall_u_denominator
from coolingnet.physics.hydraulics import (
    HAZEN_WILLIAMS_FLOW_EXPONENT,
    diameter_resistance,
    hazen_williams_coefficient,
    pump_head,
    velocity_factor,
)

TEMPERATURE_UB = 150.0


def pump_max_flow(coefficients: list[float], fallback: float) -> float:
    """Largest positive flow rate with non-negative head (zero-head point of the curve)."""
    roots = np.roots(list(reversed(coefficients)))
    real = [float(r.real) for r in roots if abs(r.imag) < 1e-9 and r.real > 0]
    return min(real) if real else fallback


def build_model(
    case: CaseStudy, spec: ProblemSpec, network: Network | None = None
) -> pyo.ConcreteModel:
    net = network or build_network(case.network)
    existing = spec.existing_design or Design.from_case(case)
    m = pyo.ConcreteModel(name="cooling_water_debottlenecking")
    m.case = case
    m.spec = spec
    m.network = net
    m.existing_design = existing

    water, econ, pipes, pumps, tower = (
        case.water,
        case.economics,
        case.pipes,
        case.pumps,
        case.cooling_tower,
    )
    rho, cp_w = water.density_kg_m3, water.cp_J_kgK
    hes = {h.edge_id: h for h in case.resolved_heat_exchangers}

    # ------------------------------------------------------------------ sets
    E = [e.id for e in net.edges]
    PI = [p.id for p in net.pipes]
    PU = [u.id for u in net.pumps]
    HE = [h.id for h in net.heat_exchangers]
    N = pipes.keys
    S = pumps.keys
    L = [c.index for c in net.circuits]
    M = list(range(len(tower.quadrature_points)))
    INT = net.interconnection_nodes

    m.E = pyo.Set(initialize=E, ordered=True)
    m.PI = pyo.Set(initialize=PI, ordered=True)
    m.PU = pyo.Set(initialize=PU, ordered=True)
    m.HE = pyo.Set(initialize=HE, ordered=True)
    m.N = pyo.Set(initialize=N, ordered=True)
    m.S = pyo.Set(initialize=S, ordered=True)
    m.L = pyo.Set(initialize=L, ordered=True)
    m.M = pyo.Set(initialize=M, ordered=True)

    # ------------------------------------------------------------ parameters
    din = {d.key: d.inner_m for d in pipes.catalogue}
    dnom = {d.key: d.nominal_in for d in pipes.catalogue}
    rres = {n: diameter_resistance(din[n]) for n in N}
    vfac = {n: velocity_factor(din[n]) for n in N}
    cpi = {n: pipe_unit_cost(dnom[n], pipes.cost_c1, pipes.cost_m) for n in N}
    hw_coef = hazen_williams_coefficient(pipes.hazen_williams_c)
    length = {p.id: p.length_m for p in net.pipes}
    exist_pipe = {
        (p.id, n): (1.0 if n == pipes.by_nominal(existing.pipe_diameters_in[p.id]).key else 0.0)
        for p in net.pipes
        for n in N
    }
    exist_pump = {
        (u.id, s): (1.0 if s == existing.pump_options[u.id] else 0.0) for u in net.pumps for s in S
    }
    r_ann = annualization_factor(econ.interest_rate, econ.project_years)
    coef = {s: list(pumps.options[s].coefficients) for s in S}
    cpu = {
        s: pump_capital_cost(
            coef[s],
            pumps.design_flow_m3_s,
            pumps.cost_FI,
            pumps.cost_Fms,
            pumps.cost_Fm,
            pumps.cost_b,
            r_ann,
        ).annualized_cost_usd_y
        for s in S
    }
    ope_factor = (
        econ.gravity_m_s2
        / pumps.efficiency
        * econ.operating_hours_per_year
        * econ.energy_cost_USD_kWh
        / 1000.0
    )
    m.params = {
        "din": din,
        "dnom": dnom,
        "cpi": cpi,
        "cpu": cpu,
        "exist_pipe": exist_pipe,
        "exist_pump": exist_pump,
        "annualization_factor": r_ann,
        "ope_factor": ope_factor,
    }

    # physically justified flow bounds (also used as big-M in Eqs. 17-18)
    q_pump_max = max(pump_max_flow(coef[s], pipes.q_max_m3_s) for s in S)
    q_ub = min(pipes.q_max_m3_s, len(PU) * q_pump_max) if spec.hydraulics else pipes.q_max_m3_s
    q_lb = pipes.q_min_m3_s
    m.q_bounds = (q_lb, q_ub)

    # heat exchanger derived data under the scenario
    he_data = {}
    for h in HE:
        d = hes[h]
        k_hot = spec.hot_flow_factor * d.hot_flow_design_kg_s
        he_data[h] = {
            "tag": d.tag,
            "C_hot": k_hot * d.cp_hot_J_kgK,
            "h_hot": d.h_hot_design_W_m2K * spec.hot_flow_factor**d.hot_film_exponent,
            "k_w_design": d.water_flow_design_kg_s,
            "pen": spec.penalty_of(case, d.tag),
            "spec": d,
        }
    m.he_data = he_data

    # ------------------------------------------------------------- variables
    q_init = _design_flow_initialization(net, hes, rho)
    m.q = pyo.Var(m.E, bounds=(q_lb, q_ub), initialize=lambda _m, e: q_init[e])

    def k(e):
        """Mass flow rate [kg/s] of edge e (Eq. k = rho q)."""
        return rho * m.q[e]

    m.k = pyo.Expression(m.E, rule=lambda _m, e: k(e))

    if spec.hydraulics:
        m.y_pi = pyo.Var(m.PI, m.N, domain=pyo.Binary, initialize=lambda _m, p, n: exist_pipe[p, n])
        m.y_pu = pyo.Var(m.PU, m.S, domain=pyo.Binary, initialize=lambda _m, u, s: exist_pump[u, s])
        # zq = q y; when y = 1 the velocity bound implies zq <= v_max pi D^2 / 4 (valid tightening)
        zq_ub = {n: min(q_ub, pipes.v_max_m_s / vfac[n]) for n in N}
        m.zq = pyo.Var(
            m.PI,
            m.N,
            bounds=lambda _m, p, n: (0.0, zq_ub[n]),
            initialize=lambda _m, p, n: exist_pipe[p, n] * min(q_init[p], zq_ub[n]),
        )
        m.v = pyo.Var(m.PI, bounds=(pipes.v_min_m_s, pipes.v_max_m_s), initialize=1.0)
        lv_ub = max(float(pump_head(q_lb, coef[s])) for s in S)
        m.lvalve = pyo.Var(m.L, bounds=(0.0, lv_ub), initialize=0.0)
        if not spec.design_free:
            for p in PI:
                for n in N:
                    m.y_pi[p, n].fix(exist_pipe[p, n])
            for u in PU:
                for s in S:
                    m.y_pu[u, s].fix(exist_pump[u, s])
        if not spec.valves_free:
            for l in L:
                m.lvalve[l].fix(0.0)

    t_wb = tower.wet_bulb_C
    water_inlet_design = {hes[h].water_inlet_design_C for h in HE}
    if len(water_inlet_design) != 1:
        raise ValueError("all heat exchangers must share the same design water inlet temperature")
    t_w_in_design = water_inlet_design.pop()

    m.T_w_in = pyo.Var(
        bounds=(0.0, TEMPERATURE_UB), initialize=t_w_in_design
    )  # basin / supply temperature
    m.T_w_feed = pyo.Var(
        bounds=(0.0, tower.max_feed_temperature_C), initialize=40.0
    )  # return to tower (Eq. 29-30)
    if spec.tower_model == "fixed_inlet":
        m.T_w_in.fix(t_w_in_design)
    else:
        m.T_w_in.setlb(t_wb)  # T_base >= T_wb

    m.cr = pyo.Var(
        m.HE,
        bounds=(1e-4, 1e4),
        initialize=lambda _m, h: he_data[h]["C_hot"] / (he_data[h]["k_w_design"] * cp_w),
    )
    m.h_w = pyo.Var(m.HE, bounds=(1e-3, None), initialize=lambda _m, h: hes[h].h_water_design_W_m2K)
    m.U = pyo.Var(
        m.HE,
        bounds=(1e-3, None),
        initialize=lambda _m, h: 0.5 * min(hes[h].h_water_design_W_m2K, he_data[h]["h_hot"]),
    )
    m.P = pyo.Var(m.HE, bounds=(1e-6, 1.0), initialize=0.4)
    m.T_hot_out = pyo.Var(
        m.HE,
        bounds=lambda _m, h: (hes[h].hot_outlet_min_C, hes[h].hot_outlet_max_C),
        initialize=lambda _m, h: hes[h].hot_outlet_spec_C,
    )
    m.T_w_out = pyo.Var(
        m.HE, bounds=(0.0, TEMPERATURE_UB), initialize=lambda _m, h: hes[h].water_outlet_design_C
    )
    for h in HE:
        d = hes[h]
        m.h_w[h].setub(
            d.h_water_design_W_m2K
            * (rho * q_ub / d.water_flow_design_kg_s) ** d.water_film_exponent
            * 1.01
        )
        m.U[h].setub(min(m.h_w[h].ub, he_data[h]["h_hot"]))
        if spec.fix_hot_outlet_to_spec:
            m.T_hot_out[h].fix(d.hot_outlet_spec_C)

    binary_penalty = spec.uses_binary_penalty
    post_penalty = spec.penalty_mode == "post"
    m.che = pyo.Var(m.HE, bounds=(0.0, None), initialize=0.0)
    if post_penalty:
        for h in HE:
            m.che[h].fix(0.0)  # evaluated after the solve (see results.Solution.from_model)
    if binary_penalty:
        m.y_he = pyo.Var(m.HE, domain=pyo.Binary, initialize=0)
        m.z_hot = pyo.Var(m.HE, bounds=lambda _m, h: (0.0, hes[h].hot_outlet_max_C), initialize=0.0)

    if spec.tower_model == "merkel":
        m.T_m = pyo.Var(m.M, bounds=(0.0, TEMPERATURE_UB), initialize=35.0)
        m.Hsat = pyo.Var(
            m.M, bounds=(0.0, None), initialize=tower.atmospheric_air_enthalpy_J_kg * 2
        )
        m.H = pyo.Var(m.M, bounds=(0.0, None), initialize=tower.atmospheric_air_enthalpy_J_kg)
        m.IM = pyo.Var(bounds=(0.0, None), initialize=1.0)
        m.IP = pyo.Var(bounds=(0.0, None), initialize=1.0)

    m.cpipe = pyo.Var(bounds=(0.0, None), initialize=0.0)
    m.cpump = pyo.Var(bounds=(0.0, None), initialize=0.0)
    m.cope = pyo.Var(bounds=(0.0, None), initialize=20000.0)
    m.cpen = pyo.Var(bounds=(0.0, None), initialize=0.0)
    m.fob = pyo.Var(initialize=0.0)

    # ----------------------------------------------------------- hydraulics
    if spec.hydraulics:
        # Eq. (1)-(2): mass balances at the interconnection nodes
        def mass_balance(_m, t):
            ti = net.node_index(t)
            return (
                sum(
                    float(net.incidence[ti, net.edge_index(e)]) * m.q[e]
                    for e in E
                    if net.incidence[ti, net.edge_index(e)] != 0
                )
                == 0
            )

        m.mass_balance = pyo.Constraint(pyo.Set(initialize=INT, ordered=True), rule=mass_balance)

        # Eq. (6), (20): a single diameter / pump option
        m.one_diameter = pyo.Constraint(m.PI, rule=lambda _m, p: sum(m.y_pi[p, n] for n in N) == 1)
        m.one_pump = pyo.Constraint(m.PU, rule=lambda _m, u: sum(m.y_pu[u, s] for s in S) == 1)

        # Eq. (17)-(18): zq = q * y (exact linearization)
        m.zq_lo1 = pyo.Constraint(
            m.PI, m.N, rule=lambda _m, p, n: m.zq[p, n] >= m.q[p] - q_ub * (1 - m.y_pi[p, n])
        )
        m.zq_up1 = pyo.Constraint(
            m.PI, m.N, rule=lambda _m, p, n: m.zq[p, n] <= m.q[p] - q_lb * (1 - m.y_pi[p, n])
        )
        m.zq_lo2 = pyo.Constraint(
            m.PI, m.N, rule=lambda _m, p, n: m.zq[p, n] >= q_lb * m.y_pi[p, n]
        )
        m.zq_up2 = pyo.Constraint(
            m.PI, m.N, rule=lambda _m, p, n: m.zq[p, n] <= q_ub * m.y_pi[p, n]
        )

        # Eq. (15)-(16): velocity bounds (v has bounds v_min..v_max)
        m.velocity = pyo.Constraint(
            m.PI, rule=lambda _m, p: m.v[p] == sum(vfac[n] * m.zq[p, n] for n in N)
        )

        if not spec.allow_downsizing:
            m.no_downsizing = pyo.Constraint(
                m.PI,
                rule=lambda _m, p: sum((m.y_pi[p, n] - exist_pipe[p, n]) * din[n] for n in N) >= 0,
            )

        # head losses (Eq. 8 with 5; Eq. 19; Eq. 31)
        def pipe_head_loss(p):
            if spec.pipe_head_formulation == "binary_product":
                return (
                    hw_coef
                    * length[p]
                    * m.q[p] ** HAZEN_WILLIAMS_FLOW_EXPONENT
                    * sum(rres[n] * m.y_pi[p, n] for n in N)
                )
            return (
                hw_coef
                * length[p]
                * sum(rres[n] * m.zq[p, n] ** HAZEN_WILLIAMS_FLOW_EXPONENT for n in N)
            )

        m.f_pipe = pyo.Expression(m.PI, rule=lambda _m, p: pipe_head_loss(p))
        m.f_pump_option = pyo.Expression(
            m.PU, m.S, rule=lambda _m, u, s: pump_head(m.q[u], coef[s])
        )
        m.f_pump = pyo.Expression(
            m.PU, rule=lambda _m, u: sum(m.y_pu[u, s] * m.f_pump_option[u, s] for s in S)
        )
        m.f_he = pyo.Expression(
            m.HE,
            rule=lambda _m, h: (
                hes[h].head_loss_design_m
                * (k(h) / hes[h].water_flow_design_kg_s) ** hes[h].head_loss_exponent
            ),
        )

        # Eq. (3): mechanical energy balance of every hydraulic circuit
        def circuit_balance(_m, l):
            c = net.circuits[l - 1]
            ids = set(c.edge_ids)
            return (
                sum(m.f_pump[u] for u in PU if u in ids)
                - net.elevation_difference_m
                - sum(m.f_he[h] for h in HE if h in ids)
                - sum(m.f_pipe[p] for p in PI if p in ids)
                - m.lvalve[l]
                == 0
            )

        m.circuit_balance = pyo.Constraint(m.L, rule=circuit_balance)

    # -------------------------------------------------------------- thermal
    # Eq. (21): CR k Cp_w = C_hot (rearranged)
    m.heat_capacity_ratio = pyo.Constraint(
        m.HE, rule=lambda _m, h: m.cr[h] * k(h) * cp_w == he_data[h]["C_hot"]
    )
    # Eq. (25)
    m.water_film = pyo.Constraint(
        m.HE,
        rule=lambda _m, h: (
            m.h_w[h]
            == hes[h].h_water_design_W_m2K
            * (k(h) / hes[h].water_flow_design_kg_s) ** hes[h].water_film_exponent
        ),
    )
    # Eq. (24)
    m.overall_u = pyo.Constraint(
        m.HE,
        rule=lambda _m, h: (
            m.U[h]
            * overall_u_denominator(
                m.h_w[h],
                he_data[h]["h_hot"],
                hes[h].tube_outer_diameter_m,
                hes[h].tube_inner_diameter_m,
                hes[h].wall_conductivity_W_mK,
                hes[h].fouling_m2K_W,
                PYOMO_OPS,
            )
            == m.h_w[h] * he_data[h]["h_hot"]
        ),
    )
    # Eq. (22)
    m.NTU = pyo.Expression(m.HE, rule=lambda _m, h: m.U[h] * hes[h].area_m2 / he_data[h]["C_hot"])

    # Eq. (26) in residual form
    def effectiveness(_m, h):
        lhs, rhs = effectiveness_residual_terms(m.NTU[h], m.cr[h], PYOMO_OPS)
        return m.P[h] * lhs == rhs

    m.effectiveness = pyo.Constraint(m.HE, rule=effectiveness)
    # Eq. (27)-(28)
    m.hot_outlet = pyo.Constraint(
        m.HE,
        rule=lambda _m, h: (
            hes[h].hot_inlet_C - m.T_hot_out[h] == m.P[h] * (hes[h].hot_inlet_C - m.T_w_in)
        ),
    )
    m.water_outlet = pyo.Constraint(
        m.HE,
        rule=lambda _m, h: (
            m.T_w_out[h] == m.T_w_in + m.cr[h] * m.P[h] * (hes[h].hot_inlet_C - m.T_w_in)
        ),
    )
    # Eq. (29): tower feed temperature (mixing of the cooler outlets); Eq. (30) is the bound of T_w_feed
    m.feed_mixing = pyo.Constraint(
        expr=m.T_w_feed * sum(k(h) for h in HE) == sum(k(h) * m.T_w_out[h] for h in HE)
    )

    # ---------------------------------------------------------- cooling tower
    if spec.tower_model == "merkel":
        k_tot = sum(k(h) for h in HE)
        alpha = tower.quadrature_points
        fit = tower.saturation_enthalpy
        m.tower_range = pyo.Constraint(expr=m.T_w_in <= m.T_w_feed)
        m.quadrature_temperature = pyo.Constraint(
            m.M,
            rule=lambda _m, i: m.T_m[i] == quadrature_temperature(m.T_w_in, m.T_w_feed, alpha[i]),
        )
        m.saturated_enthalpy = pyo.Constraint(
            m.M, rule=lambda _m, i: m.Hsat[i] == saturated_air_enthalpy(m.T_m[i], fit, PYOMO_OPS)
        )
        m.operating_line = pyo.Constraint(
            m.M,
            rule=lambda _m, i: (
                m.H[i]
                == air_enthalpy_operating_line(
                    m.T_m[i],
                    m.T_w_in,
                    k_tot,
                    tower.air_flow_kg_s,
                    tower.atmospheric_air_enthalpy_J_kg,
                    cp_w,
                )
            ),
        )
        # physical validity of the Merkel integrand: positive enthalpy driving force along the tower
        m.driving_force = pyo.Constraint(
            m.M, rule=lambda _m, i: m.Hsat[i] - m.H[i] >= tower.min_enthalpy_driving_force_J_kg
        )
        m.merkel_integral = pyo.Constraint(
            expr=m.IM
            == cp_w
            * (m.T_w_feed - m.T_w_in)
            / len(alpha)
            * sum(1.0 / (m.Hsat[i] - m.H[i] + tower.merkel_regularization_J_kg) for i in M)
        )
        m.tower_characteristic = pyo.Constraint(
            expr=m.IP * (k_tot / tower.air_flow_kg_s) ** tower.n
            == tower.packing_height_m * tower.C_un
        )
        m.merkel = pyo.Constraint(expr=m.IM == m.IP)

    # -------------------------------------------------------------- penalty
    def t_spe(h):
        return hes[h].hot_outlet_spec_C

    if binary_penalty:
        # Eqs. (50)-(54): che = pen (T_out - T_spe) y_he, linearized with z = T_out y_he
        m.penalty_value = pyo.Constraint(
            m.HE,
            rule=lambda _m, h: m.che[h] == he_data[h]["pen"] * (m.z_hot[h] - t_spe(h) * m.y_he[h]),
        )  # Eq. (52)
        m.z_lo1 = pyo.Constraint(
            m.HE,
            rule=lambda _m, h: (
                m.z_hot[h] >= m.T_hot_out[h] - hes[h].hot_outlet_max_C * (1 - m.y_he[h])
            ),
        )  # Eq. (53)
        m.z_up1 = pyo.Constraint(
            m.HE,
            rule=lambda _m, h: (
                m.z_hot[h] <= m.T_hot_out[h] - hes[h].hot_outlet_min_C * (1 - m.y_he[h])
            ),
        )
        m.z_lo2 = pyo.Constraint(
            m.HE, rule=lambda _m, h: m.z_hot[h] >= hes[h].hot_outlet_min_C * m.y_he[h]
        )  # Eq. (54)
        m.z_up2 = pyo.Constraint(
            m.HE, rule=lambda _m, h: m.z_hot[h] <= hes[h].hot_outlet_max_C * m.y_he[h]
        )
        m.penalty_active_lo = pyo.Constraint(
            m.HE,
            rule=lambda _m, h: (
                m.T_hot_out[h] - t_spe(h) >= (1 - m.y_he[h]) * (hes[h].hot_outlet_min_C - t_spe(h))
            ),
        )  # Eq. (51)
        m.penalty_active_up = pyo.Constraint(
            m.HE,
            rule=lambda _m, h: (
                m.T_hot_out[h] - t_spe(h) <= m.y_he[h] * (hes[h].hot_outlet_max_C - t_spe(h))
            ),
        )
    elif not post_penalty:
        # Epigraph of che = pen max(0, T_out - T_spe): exact because Cpen is minimized
        m.penalty_epigraph = pyo.Constraint(
            m.HE, rule=lambda _m, h: m.che[h] >= he_data[h]["pen"] * (m.T_hot_out[h] - t_spe(h))
        )

    # ---------------------------------------------------------------- costs
    if spec.hydraulics:
        m.pipe_cost = pyo.Constraint(
            expr=m.cpipe
            == sum(
                cpi[n] * length[p] * (1 - exist_pipe[p, n]) * m.y_pi[p, n] for p in PI for n in N
            )
        )  # Eq. (38)
        m.pump_cost = pyo.Constraint(
            expr=m.cpump
            == sum(cpu[s] * (1 - exist_pump[u, s]) * m.y_pu[u, s] for u in PU for s in S)
        )  # Eq. (40)
        m.operating_cost = pyo.Constraint(
            expr=m.cope == sum(m.f_pump[u] * k(u) * ope_factor for u in PU)
        )  # Eq. (47)-(48)
        if spec.budget is not None:
            m.budget = pyo.Constraint(expr=m.cpipe + m.cpump <= spec.budget)  # Eq. (46)
    else:
        m.cpipe.fix(0.0)
        m.cpump.fix(0.0)
        m.cope.fix(0.0)
    m.penalty_cost = pyo.Constraint(expr=m.cpen == sum(m.che[h] for h in HE))  # Eq. (49)

    # ------------------------------------------------------------ objective
    if spec.objective == "total_cost":
        m.objective_def = pyo.Constraint(
            expr=m.fob == m.cpipe + m.cpump + m.cope + m.cpen
        )  # Eq. (55)
    elif spec.objective == "cost_without_penalty":
        m.objective_def = pyo.Constraint(expr=m.fob == m.cpipe + m.cpump + m.cope)
    elif spec.objective == "flow_deviation":
        if not spec.target_flows_kg_s:
            raise ValueError("objective 'flow_deviation' requires target_flows_kg_s")
        m.objective_def = pyo.Constraint(
            expr=m.fob
            == spec.flow_deviation_scale
            * sum((k(h) - spec.target_flows_kg_s[he_data[h]["tag"]]) ** 2 for h in HE)
        )
    else:  # pragma: no cover
        raise ValueError(f"unknown objective {spec.objective!r}")
    m.obj = pyo.Objective(expr=m.fob, sense=pyo.minimize)
    add_scaling_suffix(m)
    return m


def add_scaling_suffix(m: pyo.ConcreteModel) -> None:
    """Attach `scaling_factor` suffixes (variable and constraint) for interior point solvers."""
    sf = m.scaling_factor = pyo.Suffix(direction=pyo.Suffix.EXPORT)
    spec: ProblemSpec = m.spec
    temp, cost, enth = 0.02, 1e-4, 1e-5
    for e in m.E:
        sf[m.q[e]] = 10.0
    if spec.hydraulics:
        for p in m.PI:
            sf[m.v[p]] = 1.0
            for n in m.N:
                sf[m.zq[p, n]] = 10.0
                for con in (m.zq_lo1, m.zq_up1, m.zq_lo2, m.zq_up2):
                    sf[con[p, n]] = 10.0
            sf[m.velocity[p]] = 1.0
            sf[m.one_diameter[p]] = 1.0
        for l in m.L:
            sf[m.lvalve[l]] = 0.1
            sf[m.circuit_balance[l]] = 0.1
        for t in m.mass_balance:
            sf[m.mass_balance[t]] = 10.0
        sf[m.pipe_cost] = cost
        sf[m.pump_cost] = cost
        sf[m.operating_cost] = cost
        if hasattr(m, "budget"):
            sf[m.budget] = cost
    sf[m.T_w_in] = temp
    sf[m.T_w_feed] = temp
    sf[m.feed_mixing] = 1e-3
    for h in m.HE:
        sf[m.cr[h]] = 1.0
        sf[m.h_w[h]] = 1e-4
        sf[m.U[h]] = 1e-3
        sf[m.P[h]] = 1.0
        sf[m.T_hot_out[h]] = temp
        sf[m.T_w_out[h]] = temp
        sf[m.che[h]] = cost
        sf[m.heat_capacity_ratio[h]] = 1.0 / max(abs(m.he_data[h]["C_hot"]), 1.0)
        sf[m.water_film[h]] = 1e-4
        sf[m.overall_u[h]] = 1.0 / max(m.he_data[h]["h_hot"] * 1e4, 1.0)
        sf[m.effectiveness[h]] = 1.0
        sf[m.hot_outlet[h]] = 0.1
        sf[m.water_outlet[h]] = 0.1
        if spec.uses_binary_penalty:
            sf[m.z_hot[h]] = temp
            for con in (m.penalty_value,):
                sf[con[h]] = cost
            for con in (
                m.z_lo1,
                m.z_up1,
                m.z_lo2,
                m.z_up2,
                m.penalty_active_lo,
                m.penalty_active_up,
            ):
                sf[con[h]] = temp
        elif spec.penalty_mode == "epigraph":
            sf[m.penalty_epigraph[h]] = cost
    if spec.tower_model == "merkel":
        for i in m.M:
            sf[m.T_m[i]] = temp
            sf[m.Hsat[i]] = enth
            sf[m.H[i]] = enth
            sf[m.quadrature_temperature[i]] = temp
            sf[m.saturated_enthalpy[i]] = enth
            sf[m.operating_line[i]] = enth
            sf[m.driving_force[i]] = enth
        sf[m.IM] = 1.0
        sf[m.IP] = 1.0
        sf[m.merkel_integral] = 1.0
        sf[m.tower_characteristic] = 1.0
        sf[m.merkel] = 1.0
        sf[m.tower_range] = temp
    for var in (m.cpipe, m.cpump, m.cope, m.cpen, m.fob):
        sf[var] = cost
    sf[m.penalty_cost] = cost
    sf[m.objective_def] = cost if spec.objective != "flow_deviation" else 1e-3
    sf[m.obj] = cost if spec.objective != "flow_deviation" else 1e-3


def initialize_from_simulation(m: pyo.ConcreteModel, sim) -> None:
    """Set every variable from a `SimulationResult` of the same design (good interior start)."""
    net: Network = m.network
    case: CaseStudy = m.case
    cp_w = case.water.cp_J_kgK
    spec: ProblemSpec = m.spec
    tower = case.cooling_tower
    v = pyo.value

    def setv(var, val):
        if var.fixed:
            return
        lo = var.lb if var.lb is not None else -math.inf
        hi = var.ub if var.ub is not None else math.inf
        var.set_value(min(max(float(val), lo), hi), skip_validation=True)

    for e in net.edges:
        setv(m.q[e.id], sim.edge_flows_m3_s[e.id])
    if spec.hydraulics:
        dnom = m.params["dnom"]
        for p in net.pipes:
            d_sel = m.existing_design.pipe_diameters_in[p.id]
            for n in m.N:
                y = 1.0 if abs(dnom[n] - d_sel) < 1e-9 else 0.0
                setv(m.y_pi[p.id, n], y)
                setv(m.zq[p.id, n], y * sim.edge_flows_m3_s[p.id])
            setv(m.v[p.id], sim.details["velocities_m_s"][p.id])
        for u in net.pumps:
            for s_ in m.S:
                setv(m.y_pu[u.id, s_], 1.0 if s_ == m.existing_design.pump_options[u.id] else 0.0)
        for c in net.circuits:
            setv(m.lvalve[c.index], sim.valve_head_losses_m.get(c.index, 0.0))
    setv(m.T_w_in, sim.T_w_in_C)
    setv(m.T_w_feed, sim.T_w_feed_C)
    for h in net.heat_exchangers:
        x = sim.exchangers[h.tag]
        d = m.he_data[h.id]
        setv(m.cr[h.id], x["CR"])
        setv(m.U[h.id], x["U_W_m2K"])
        setv(m.P[h.id], x["effectiveness"])
        setv(m.T_hot_out[h.id], x["T_hot_out_C"])
        setv(m.T_w_out[h.id], x["T_w_out_C"])
        spec_he = d["spec"]
        setv(
            m.h_w[h.id],
            spec_he.h_water_design_W_m2K
            * (x["k_kg_s"] / spec_he.water_flow_design_kg_s) ** spec_he.water_film_exponent,
        )
        pen_val = d["pen"] * max(0.0, x["T_hot_out_C"] - spec_he.hot_outlet_spec_C)
        setv(m.che[h.id], pen_val)
        if spec.uses_binary_penalty:
            active = 1.0 if x["T_hot_out_C"] > spec_he.hot_outlet_spec_C else 0.0
            setv(m.y_he[h.id], active)
            setv(m.z_hot[h.id], active * x["T_hot_out_C"])
    if spec.tower_model == "merkel":
        from coolingnet.physics.cooling_tower import (
            air_enthalpy_operating_line,
            quadrature_temperature,
            saturated_air_enthalpy,
            tower_characteristic,
        )

        k_tot = sum(x["k_kg_s"] for x in sim.exchangers.values())
        for i, alpha in enumerate(tower.quadrature_points):
            t_m = quadrature_temperature(sim.T_w_in_C, sim.T_w_feed_C, alpha)
            setv(m.T_m[i], t_m)
            setv(m.Hsat[i], saturated_air_enthalpy(t_m, tower.saturation_enthalpy))
            setv(
                m.H[i],
                air_enthalpy_operating_line(
                    t_m,
                    sim.T_w_in_C,
                    k_tot,
                    tower.air_flow_kg_s,
                    tower.atmospheric_air_enthalpy_J_kg,
                    cp_w,
                ),
            )
        ip = tower_characteristic(
            k_tot / tower.air_flow_kg_s, tower.packing_height_m, tower.C_un, tower.n
        )
        setv(m.IP, ip)
        setv(m.IM, ip)
    setv(m.cope, sim.operating_cost_USD_y)
    setv(m.cpen, sum(v(m.che[h.id]) for h in net.heat_exchangers))
    setv(m.cpipe, 0.0)
    setv(m.cpump, 0.0)
    setv(m.fob, v(m.cpipe) + v(m.cpump) + v(m.cope) + v(m.cpen))


def _design_flow_initialization(net: Network, hes, rho: float) -> dict:
    """Initial flow rates: design water flow of each cooler propagated along its circuit."""
    q_circ = {c.index: hes[c.he_edge].water_flow_design_kg_s / rho for c in net.circuits}
    out = {}
    for e in net.edges:
        out[e.id] = sum(q_circ[c.index] for c in net.circuits if e.id in c.edge_ids)
    return out


def selected_design(m: pyo.ConcreteModel) -> Design:
    """Read the pipe diameters / pump options chosen in a solved model."""
    net: Network = m.network
    if not m.spec.hydraulics:
        return m.existing_design
    dnom = m.params["dnom"]
    pipes = {}
    for p in net.pipes:
        best = max(m.N, key=lambda n: pyo.value(m.y_pi[p.id, n]))
        pipes[p.id] = dnom[best]
    pumps = {}
    for u in net.pumps:
        pumps[u.id] = max(m.S, key=lambda s: pyo.value(m.y_pu[u.id, s]))
    return Design(pipe_diameters_in=pipes, pump_options=pumps)
