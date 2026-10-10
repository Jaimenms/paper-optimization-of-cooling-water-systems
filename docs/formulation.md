# Formulation: equation ↔ code map

Paper: J.N.M. Souza, A.L.L. Levy, A.L.H. Costa, *Optimization of cooling water system hydraulic
debottlenecking*, Applied Thermal Engineering 128 (2018) 1531–1542,
doi:10.1016/j.applthermaleng.2017.09.089. Equation numbers refer to the published article.

The optimization model of the paper (Section 2) is implemented in
[`src/coolingnet/optimization/model.py`](../src/coolingnet/optimization/model.py) with Pyomo.
Physical and economic relations are shared with the NumPy simulator through
[`src/coolingnet/physics`](../src/coolingnet/physics) and
[`src/coolingnet/economics`](../src/coolingnet/economics) (single source of truth).

| Paper | Meaning | Code |
|---|---|---|
| Eq. (1)-(2) | mass balances at the interconnection nodes | `m.mass_balance` (incidence matrix from `network/graph.py`) |
| Eq. (3) | mechanical energy balance of every hydraulic circuit | `m.circuit_balance` (circuit matrix Λ from `network/graph.py`) |
| Eq. (4), (8) | Hazen-Williams head loss, diameter selection | `physics/hydraulics.py: hazen_williams_head_loss`, `m.f_pipe` |
| Eq. (6) | one commercial diameter per pipe | `m.one_diameter` |
| Eq. (15)-(18) | velocity bounds with the linearization `zq = q·y` | `m.velocity`, `m.zq_lo1 … m.zq_up2`, bounds of `m.v` |
| Eq. (19)-(20) | pump curve and single pump option | `physics/hydraulics.py: pump_head`, `m.f_pump`, `m.one_pump` |
| Eq. (21) | heat capacity ratio | `m.heat_capacity_ratio` |
| Eq. (22) | NTU | `m.NTU` (expression) |
| Eq. (24) | overall heat transfer coefficient (rearranged) | `physics/heat_exchanger.py: overall_u_denominator`, `m.overall_u` |
| Eq. (25) | water film coefficient power law | `m.water_film` |
| Eq. (26) | effectiveness, 1 shell pass / even tube passes | `physics/heat_exchanger.py: effectiveness_residual_terms`, `m.effectiveness` |
| Eq. (27)-(28) | outlet temperatures | `m.hot_outlet`, `m.water_outlet` |
| Eq. (29)-(30) | tower feed temperature and its bound | `m.feed_mixing`, bounds of `m.T_w_feed` |
| Eq. (31) | cooler head loss power law | `m.f_he` |
| Eq. (32)-(37) | Merkel equation, quadrature, operating line, saturation enthalpy, tower characteristic | `physics/cooling_tower.py`, `m.quadrature_temperature`, `m.saturated_enthalpy`, `m.operating_line`, `m.merkel_integral`, `m.tower_characteristic`, `m.merkel` |
| Eq. (38)-(39) | pipe capital cost (Narang et al.) | `economics/costs.py: pipe_unit_cost`, `m.pipe_cost` |
| Eq. (40)-(45) | pump capital cost (Couper et al.), annualization | `economics/costs.py: pump_capital_cost, annualization_factor`, `m.pump_cost` |
| Eq. (46) | budget constraint | `m.budget` (only when `ProblemSpec.budget` is not `None`) |
| Eq. (47)-(48) | operating cost | `economics/costs.py: pump_operating_cost`, `m.operating_cost` |
| Eq. (49)-(54) | penalties (binary big-M formulation) | `m.penalty_value`, `m.z_*`, `m.penalty_active_*` (`penalty_formulation="binary"`) |
| — | penalties, epigraph form `che ≥ pen (T_out − T_spe)`, `che ≥ 0` | `m.penalty_epigraph` (default when Cpen is minimized; exact and better conditioned) |
| Eq. (55) | objective function | `m.objective_def`, `m.obj` |
| Section 3.7 | purely hydraulic objective (sum of squared flow deviations) | `ProblemSpec(objective="flow_deviation")` |

## Differences between the published text and the original GAMS code

The GAMS sources that generated the published results (`legacy/gams`, the authors' own
code) differ from the paper text in two places (formal errata in [`errata.md`](errata.md)). The configuration file keeps the **code** values because they are
the ones that reproduce the published tables:

* Merkel quadrature abscissae: text `(0.1, 0.4, 0.6, 0.9)`, code `(0.1, 0.4, 0.6, 0.7)`
  (`cooling_tower.quadrature_points`).
* Hazen-Williams: the exponent of `c` is 1.85 (text and code) while the flow exponent is 1.852.

Other implementation details that are not spelled out in the paper but are present in the code:

* **Positive enthalpy driving force in the tower** (`m.driving_force`): `Hsat_m - H_m >= 100 J/kg`
  at every quadrature point (`cooling_tower.min_enthalpy_driving_force_J_kg`). This constraint is
  not in the paper nor in the GAMS code, but it is a physical requirement of the Merkel method
  (the air must stay unsaturated along the packing). Without it, the regularized integrand
  `1/(Hsat - H + 1)` changes sign where the operating line crosses the saturation curve and the
  equation `IM = IP` acquires a *spurious* root at the lower bound `T_base = T_wb`: during the
  port, Bonmin found a "zero-penalty" design for Case 2 (53.4 kUSD/y) whose tower delivered water
  at the wet-bulb temperature with a negative driving force at the top of the packing. The
  published solutions all have driving forces above 40 kJ/kg, so the constraint does not affect
  them; it only removes the non-physical branch. The NumPy simulator applies the same rule when
  it selects the root of the Merkel equation.

* `q_min = 1e-5 m3/s` and the big-M `q_max` of Eqs. (17)-(18); the Python model uses the
  zero-head flow rate of the strongest pump as `q_max` (tighter and mathematically equivalent).
* The Merkel integral denominator is regularized with `+1 J/kg`
  (`cooling_tower.merkel_regularization_J_kg`).
* The water inlet temperature of every cooler equals the tower basin temperature
  (single supply header).

## Solution strategy

* **`nlpbb` (default)** — an NLP-based branch-and-bound written in
  [`optimization/nlpbb.py`](../src/coolingnet/optimization/nlpbb.py), the same algorithmic family
  as the SBB + CONOPT pair used in the paper: the Pyomo model is scaled (`core.scale_model`),
  translated once to CasADi, and every node is an IPOPT solve of the NLP relaxation with
  modified bounds. Branching uses SOS1-style dichotomies over the ordered one-hot groups
  (`y_pi[p, :]` over the catalogue, `y_pu[u, :]` over the pump options), node selection is
  best-first, termination follows `optcr`/`optca` (relative/absolute gap 1e-3 as in the GAMS
  runs). Three safeguards address the non-convexity (the valve sub-problem alone has several
  local optima): integral nodes are polished with a **multi-start** on the valve head losses
  (open valves, random throttling, parent and root points); a node is **pruned only after a
  second NLP solve** from the root point confirms its value; and the final design is improved
  by a **first-improvement local search** over adjacent catalogue diameters and the other pump
  options (`SolverSettings.local_search_steps`, 0 disables). Case 1 and Case 2 take about 5 s;
  the budget-limited cases 10-25 s; the full set of paper scenarios (budget and penalty sweeps
  included) runs in roughly half an hour. The model is initialized from the NumPy simulation
  of the existing design (`initialize_from_simulation`).
* **Bonmin (B-BB)** through CasADi: the reference external implementation of the same idea;
  available with `SolverSettings(name="bonmin")`. It reproduces Case 1 in ~30 s but its C++
  branch-and-bound occasionally aborts on this problem, which is why it is not the default.
* **IPOPT**: used automatically when no integer variable is free (simulations, valve-only runs).
* **Robustness** (`optimization/problems.py`, `optimization/isolation.py`): every branch-and-bound
  runs in a separate interpreter; a crash is retried once with conservative Bonmin settings
  (`most-fractional` branching, no random resolves) and, failing that, the best known feasible
  design (warm start or existing network) is kept and only the valves are re-optimized (IPOPT).
  Warm starts from a feasible design also provide a `cutoff` to the branch-and-bound. Sweeps
  therefore never abort; the `report` of every `Solution` records what happened.
* **SCIP** (`pyscipopt`): global solver available for cross-checks; the dual bound of this
  non-convex MINLP is weak, so it is not the default.
* Any Pyomo-registered executable (`bonmin`, `couenne`, `scip`, `ipopt`) can also be used.

Like the SBB solutions of the paper, the solutions of every back-end are local optima of a
non-convex problem; the reproduction status of each table and figure is in
[`reproduction.md`](reproduction.md).
