# Errata

Erratum to: J.N.M. Souza, A.L.L. Levy, A.L.H. Costa, **Optimization of cooling water system
hydraulic debottlenecking**, *Applied Thermal Engineering* 128 (2018) 1531–1542,
https://doi.org/10.1016/j.applthermaleng.2017.09.089.

Items identified during the independent reimplementation of the model (`coolingnet`), by
confronting the published text, the GAMS code that generated the results
(`legacy/gams/coolingnetwork_applied_v21_part0.gms`) and the numerical reproduction of the
tables. Severity: **high** = changes published numbers; **medium** = gap in the formulation
without effect on the numbers; **low** = typographical or without consequence. The Portuguese
working version is [`pt/errata.md`](pt/errata.md); the reproduction status is in
[`reproduction.md`](reproduction.md).

| Id | Location in the paper | Problem | Severity |
|----|-----------------------|---------|----------|
| [E1](#e1) | Section 2.2.5, text after Eq. (34), p. 1536 | Abscissa α₄ printed as 0.9; results computed with 0.7 | High |
| [E2](#e2) | Section 2.2.5, Eqs. (32)–(36), pp. 1535–1536 | Missing positive driving force condition `Hsat_m − H_m > 0`; regularization used in the code not mentioned | Medium |
| [E3](#e3) | Section 2.2.2, Eq. (4), p. 1534 | Exponent of `c` printed as 1.85 (Hazen-Williams: 1.852) | Low |
| [E4](#e4) | Nomenclature, p. 1532 | Unit of `H` (air enthalpy) printed as J/°C | Low |
| [E5](#e5) | Section 3.1, Table 7, p. 1538 | Water viscosity listed but not used by the model | Low |

---

## E1

**Location.** Section 2.2.5 (*Cooling tower model*), paragraph introducing Eq. (35): "the
cooling water temperature along the quadrature points (α₁ = 0.1, α₂ = 0.4, α₃ = 0.6,
α₄ = 0.9)".

**Published text.** α₄ = 0.9 (the four-point Chebyshev abscissae 0.1, 0.4, 0.6, 0.9 of the
Merkel integral, standard in the cooling tower literature).

**Correction.** The code that generated every result used α₄ = **0.7**
(`Parameter alfa_torre(m_Merkel) / 1 0.1, 2 0.4, 3 0.6, 4 0.7 /`). The text is correct about the
method, but the tables and figures do not correspond to the printed value. Suggested wording:
replace "α₄ = 0.9" by "α₄ = 0.7" with a note that the numerical results used this abscissa (which
differs from the 0.9 of the four-point Chebyshev rule); or, alternatively, state that the results
corrected with α₄ = 0.9 are those of the tables below.

**Evidence.** The reimplementation reproduces Table 8 to three decimals only with α₄ = 0.7
(basin temperature 32.202 °C in the initial condition and 32.824 °C in the current one,
identical to the GAMS listings `part2_initial.lst` and `part2_actual.lst`). With α₄ = 0.9 the
values change.

**Impact.** Recomputed with the reimplementation (`nlpbb` solver, same data); values in kUSD/y
unless stated; "published" = α₄ = 0.7, "corrected" = α₄ = 0.9.

Table 8 — hot stream outlet temperatures (°C) and penalties in the current condition:

| Exchanger | Initial publ. | Initial corr. | Current publ. | Current corr. | Penalty publ. | Penalty corr. |
|-----------|------:|------:|------:|------:|------:|------:|
| E-101 | 63.48 | 63.45 | 65.16 | 65.12 | 1.96 | 1.55 |
| E-102 | 78.39 | 78.35 | 81.59 | 81.54 | 19.82 | 19.25 |
| E-103 | 39.66 | 39.60 | 41.82 | 41.73 | 22.70 | 21.65 |
| E-104 | 40.91 | 40.85 | 42.81 | 42.73 | 22.61 | 21.67 |
| E-105 | 39.75 | 39.69 | 41.53 | 41.45 | 6.62 | 5.64 |
| Total | | | | | **73.71** | **69.75** |

Basin temperature: 32.20 → 32.13 °C (initial) and 32.82 → 32.72 °C (current).

Table 9 — no available budget:

| Quantity | Published | Corrected |
|----------|------:|------:|
| Optimal flow rates E-101..E-105 (kg/s) | 12.65 / 23.04 / 33.69 / 17.21 / 3.58 | 12.46 / 23.55 / 34.63 / 16.90 / 3.51 |
| Valve head losses (m) | 0.49 / 3.70 / 1.90 / 0 / 0 | 0.48 / 3.28 / 1.36 / 0 / 0 |
| Total penalty | 68.40 | 64.33 |
| Objective function | 88.87 | 84.76 |
| Penalty reduction vs. current condition | 7.2 % | 7.8 % |

Tables 10 and 11 and Figs. 9–10 — objective function, penalty and interventions:

| Case | Objective publ. | Objective corr. | Penalty publ. | Penalty corr. | Interventions publ. | Interventions corr. |
|------|------:|------:|------:|------:|---|---|
| No budget | 88.87 | 84.76 | 68.40 | 64.33 | valves | valves |
| 1A (B = 2.625) | 86.93 | 83.75 | 64.18 | 60.97 | pipes 5 and 6 → 8 in | same |
| 1B (B = 4.125) | 85.04 | 83.31 | 54.20 | 52.43 | pump 4 | pump 4 |
| 1C (B = 5.250) | 84.77 | 83.18 | 52.85 | 51.18 | pump 4 + pipe 5 → 8 in | pump 4 + pipe 6 → 8 in |
| Case 1 (unlimited) | 84.59 | 83.08 | 51.54 | 49.94 | pump 4 + pipes 5 and 6 → 8 in | same |
| Case 2 (pen = 40) | 189.78 | 186.14 | 150.57 | 147.00 | pump 4 + 10 pipes | pump 4 + 9 pipes |

Penalty reductions of Fig. 10 with the corrected value: 7.8 % (no budget), 12.6 % (1A), 24.8 %
(1B), 26.6 % (1C) and 28.4 % (Case 1), against the published 7.21 / 12.95 / 26.48 / 28.3 /
30.08 %. The curves of Figs. 4, 7 and 8 shift in the same proportion; the steps (order of the
interventions) remain.

**Consequence for the conclusions.** No qualitative conclusion changes: the ranking of the
cases, the jump to the pump purchase near 3 kUSD/y and the comparison with the purely
hydraulic approach (Table 12, whose desired flow rates do not depend on the tower) remain
valid. The absolute values of penalty and objective function are overestimated by 2–6 %.

## E2

**Location.** Section 2.2.5, Eqs. (32)–(36); in particular the integrand of Eq. (33),
`1/(Hsat_m − H_m)`.

**Published text.** The formulation does not impose `Hsat_m − H_m > 0` (unsaturated air along the
packing), a necessary condition for the Merkel integral to be meaningful. Moreover, the code
used the regularization `1/(Hsat_m − H_m + 1)` (1 J/kg), not mentioned in the paper. With the
regularization, the integrand changes sign where the operating line crosses the saturation
curve and Eq. (32) admits a spurious root at the wet-bulb temperature.

**Evidence.** During the reproduction of Case 2 one solver (Bonmin) converged to a design with
zero penalty and a total cost of 53.4 kUSD/y, against the published 189.8 kUSD/y; at that point
the basin was at 26.5 °C (= wet bulb, zero approach) and `Hsat − H = −4.2 kJ/kg` at the upper
quadrature point. With the constraint `Hsat_m − H_m ≥ 100 J/kg` added, the same solver
reproduces the published solution.

**Impact on the published results.** None. All solutions of the paper satisfy the condition
with a wide margin (driving forces above ~40 kJ/kg), because SBB/CONOPT started from physical
points and never migrated to the other branch.

**Consequence.** Readers implementing the formulation as published, with another solver or
another starting point, may obtain non-physical solutions that seem to eliminate the penalties
at low cost, contradicting the discussion of Section 3.4 ("the solutions do not eliminate the
set-point penalties entirely").

**Correction.** Add to the formulation the constraint `Hsat_m − H_m ≥ ε, m = 1, …, 4` (ε small
and positive) and mention the numerical regularization used, or state explicitly
`T_in_w > T_wb` together with the unsaturated-air condition.

## E3

**Location.** Section 2.2.2, Eq. (4): `fpi_k = 10.67 q_k^1.852 / (c^1.85 D_k^4.8704)`.

**Published text.** Exponent 1.85 on the Hazen-Williams coefficient `c`.

**Correction.** The exponent of `c` in the SI form of the Hazen-Williams equation is
1/0.54 = 1.852, the same as that of `q`; the printed 1.85 is a rounding. The code uses the printed
value, so text and results are consistent with each other. Write `c^1.852` (and, if desired,
mention that the calculations used 1.85).

**Impact.** `120^(1.852−1.85) ≈ 1.010`: the pipe head losses are about 1 % higher than with the
standard exponent. The effect on flow rates and costs is below the precision of the tables; no
effect on the conclusions.

## E4

**Location.** Nomenclature, entry "H air enthalpy (J/°C)".

**Correction.** The specific enthalpy of air is expressed in J/kg (as `Hatm` in Table 7,
71 000 J/kg).

**Impact.** Typographical.

## E5

**Location.** Section 3.1, Table 7, row "Cooling water viscosity (mPa·s) 0.72".

**Correction.** The viscosity does not enter any equation of the model (head losses by
Hazen-Williams, film coefficients by power laws from the design conditions). The parameter can
be omitted, or the text can clarify that it was used only in the original sizing of the
exchangers (Table 6).

**Impact.** None.
