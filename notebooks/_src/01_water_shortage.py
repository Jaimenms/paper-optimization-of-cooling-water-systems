# %% [markdown]
# # 01 · Water shortage - Table 8
#
# Section 3.2 of the paper: the hot stream flow rates increased by 20 % during the plant
# lifetime (shell-side film coefficients follow a power law with exponent 0.6), but the cooling
# water system was not modified. The existing network is **simulated** (fixed pipes, pump and
# fully open valves) for the initial and the current conditions.
#
# Two independent implementations are compared: a NumPy/SciPy simulator (hydraulic balance +
# P-NTU coolers + Merkel tower) and the Pyomo model solved as a square NLP with IPOPT.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from coolingnet import paper_case
from coolingnet.optimization import SolverSettings
from coolingnet.reporting import paper_reference as REF
from coolingnet.reporting import tables as T
from coolingnet.simulation import simulate_design
from coolingnet.workflow import PaperPipeline, PipelineConfig

RESULTS_DIR = Path("../results")  # produced by `coolingnet run`; re-used by every notebook
FORCE_RESOLVE = False  # True: ignore cached results and solve again

case = paper_case()
factor = case.scenarios.hot_flow_increase_factor
pipeline = PaperPipeline(case, PipelineConfig(results_dir=RESULTS_DIR, force=FORCE_RESOLVE, solver=SolverSettings(name="nlpbb", time_limit_s=600)))

# %% [markdown]
# ## NumPy/SciPy simulation of the existing design

# %%
sim_initial = simulate_design(case, hot_flow_factor=1.0)
sim_current = simulate_design(case, hot_flow_factor=factor)
rows = []
for tag in sim_initial.exchangers:
    rows.append(
        {
            "Heat exchanger": tag,
            "Design condition (C)": case.heat_exchanger(tag).hot_outlet_spec_C,
            "Initial condition (C)": sim_initial.exchangers[tag]["T_hot_out_C"],
            "Current condition (C)": sim_current.exchangers[tag]["T_hot_out_C"],
            "Current condition penalty (kUSD/y)": sim_current.exchangers[tag]["penalty_USD_y"] / 1e3,
            "Water flow (kg/s)": sim_current.exchangers[tag]["k_kg_s"],
        }
    )
table8_numpy = pd.DataFrame(rows).set_index("Heat exchanger")
display(table8_numpy.round(2))
print(f"tower: T_w,in = {sim_current.T_w_in_C:.2f} C, T_feed = {sim_current.T_w_feed_C:.2f} C; "
      f"operating cost = {sim_current.operating_cost_USD_y / 1e3:.2f} kUSD/y; total penalty = {sim_current.penalty_USD_y / 1e3:.2f} kUSD/y")

# %% [markdown]
# ## Table 8 with the optimization model (Pyomo + IPOPT) and comparison with the paper

# %%
sims = pipeline.run_simulations()
table8 = T.table_heat_exchangers_performance(case, sims["initial"], sims["current"])
display(table8.round(2))
display(REF.compare(REF.TABLE8, table8.drop(index="Total")).round(2))
print("paper total penalty:", REF.TABLE8_TOTAL_PENALTY, "kUSD/y  |  this work:", round(table8.loc["Total", "Current condition penalty (kUSD/y)"], 2))

# %% [markdown]
# The outlet temperatures at the initial operation are lower than the design values (excess area),
# while the current condition violates every set-point. Both implementations agree with the paper
# to the published precision.

# %%
fig, ax = plt.subplots(figsize=(7, 4))
tags = list(table8.index[:-1])
x = range(len(tags))
w = 0.27
ax.bar([i - w for i in x], table8.loc[tags, "Design condition (C)"], w, color="black", label="Design task")
ax.bar(list(x), table8.loc[tags, "Initial condition (C)"], w, color="0.6", label="Initial condition")
ax.bar([i + w for i in x], table8.loc[tags, "Current condition (C)"], w, color="lightblue", edgecolor="black", label="Current condition")
ax.set_xticks(list(x))
ax.set_xticklabels(tags)
ax.set_ylabel("Hot stream outlet temperature (°C)")
ax.set_ylim(20, 95)
ax.legend()
ax.set_title("Hot stream outlet temperatures of the existing network")
plt.show()

# %% [markdown]
# ## A note on the Merkel quadrature points
#
# The paper text lists the abscissae $\alpha_m$ = (0.1, 0.4, 0.6, 0.9) for the 4-point
# Chebyshev integration of the Merkel integral, but the GAMS code that produced the published
# results used (0.1, 0.4, 0.6, **0.7**). The configuration keeps the code value so that the
# tables match; the cell below shows the (small) effect of the textbook value.

# %%
alt_tower = case.cooling_tower.model_copy(update={"quadrature_points": [0.1, 0.4, 0.6, 0.9]})
sim_alt = simulate_design(case.with_updates(cooling_tower=alt_tower), hot_flow_factor=1.0)
pd.DataFrame(
    {
        "alpha4 = 0.7 (code, paper tables)": [sim_initial.T_w_in_C, sim_initial.T_w_feed_C] + [v["T_hot_out_C"] for v in sim_initial.exchangers.values()],
        "alpha4 = 0.9 (paper text)": [sim_alt.T_w_in_C, sim_alt.T_w_feed_C] + [v["T_hot_out_C"] for v in sim_alt.exchangers.values()],
    },
    index=["T_w,in (C)", "T_feed (C)"] + [f"T_hot,out {t} (C)" for t in sim_initial.exchangers],
).round(3)
