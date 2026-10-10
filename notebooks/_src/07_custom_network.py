# %% [markdown]
# # 07 · Configuring your own network and parameters
#
# The model is generic: any digraph of pipes, a pump and coolers in parallel between the tower
# basin and the tower top can be optimized. This notebook adds a **sixth cooler (E-106)** in
# parallel to E-105, changes a few parameters, validates the new structure, simulates the
# current condition and solves two debottlenecking problems.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from coolingnet import build_network, paper_case
from coolingnet.config import dump_case, load_case
from coolingnet.config.schema import CaseStudy, HeatExchangerEdge, HeatExchangerSpec, PipeEdge
from coolingnet.optimization import SolverSettings
from coolingnet.optimization.problems import optimize_debottlenecking, simulate_existing_network
from coolingnet.reporting import figures as F
from coolingnet.reporting import plot_network
from coolingnet.reporting import tables as T
from coolingnet.simulation import simulate_design

base = paper_case()

# %% [markdown]
# ## 1. Describe the new topology
#
# New nodes 21 (before E-106) and 22 (after it); pipe 24 feeds E-106 from node 6 and pipe 25
# returns the water to node 7. Drawing coordinates are optional (an automatic layered layout is used
# otherwise), but keep the picture readable.

# %%
edges = list(base.network.edges) + [
    PipeEdge(id=24, tail=6, head=21, length_m=40.0, diameter_in=3.0),
    HeatExchangerEdge(id=26, tail=21, head=22, tag="E-106"),
    PipeEdge(id=25, tail=22, head=7, length_m=40.0, diameter_in=3.0),
]
layout = dict(base.network.layout)
layout.update({21: (9.0, 1.0), 22: (9.0, 2.0)})
network = base.network.model_copy(update={"edges": edges, "layout": layout})

# the cooler data (Tables 5-6 style). Fields left out fall back to `heat_exchanger_defaults`.
e106 = HeatExchangerSpec(
    area_m2=35.0,
    hot_flow_design_kg_s=4.0,
    water_flow_design_kg_s=8.0,
    hot_inlet_C=75.0,
    hot_outlet_spec_C=45.0,
    water_inlet_design_C=32.0,
    water_outlet_design_C=40.0,
    cp_hot_J_kgK=2300.0,
    h_water_design_W_m2K=5200.0,
    h_hot_design_W_m2K=400.0,
    fouling_m2K_W=5.0e-4,
    head_loss_design_m=2.5,
    penalty_factor_USD_per_C_y=20000.0,  # a more valuable product in this cooler
)
custom = CaseStudy(
    name="Paper network + E-106",
    network=network,
    heat_exchangers={**base.heat_exchangers, "E-106": e106},
    heat_exchanger_defaults=base.heat_exchanger_defaults,
    pipes=base.pipes,
    pumps=base.pumps,
    cooling_tower=base.cooling_tower.model_copy(update={"air_flow_kg_s": 70.0}),  # a slightly larger tower fan
    water=base.water,
    economics=base.economics.model_copy(update={"energy_cost_USD_kWh": 0.12}),
    scenarios=base.scenarios,
)
net = build_network(custom.network)
fig, ax = plt.subplots(figsize=(12, 5))
plot_network(custom, ax=ax, title=custom.name)
display(T.table_circuits(custom, net))

# %% [markdown]
# The configuration can be saved and later loaded with `load_case(...)` (or passed to the CLI with
# `coolingnet run --config my_network.yaml`).

# %%
path = dump_case(custom, Path("../configs/example_six_coolers.yaml"))
reloaded = load_case(path)
assert reloaded == custom
print("saved to", path)

# %% [markdown]
# ## 2. Simulate the current condition (hot flow rates +20 %)

# %%
sim = simulate_design(custom, hot_flow_factor=custom.scenarios.hot_flow_increase_factor)
pd.DataFrame(sim.exchangers).T[["k_kg_s", "T_hot_out_C", "T_hot_out_spec_C", "penalty_USD_y", "head_loss_m"]].astype(float).round(2)

# %% [markdown]
# ## 3. Optimize: valves only, then a finite budget
#
# `optimize_debottlenecking` accepts `budget=None` (unlimited), `budget=0.0` (valves only) or a
# positive value; `penalty_factor` and `hot_flow_factor` can also be overridden per call.

# %%
settings = SolverSettings(name="nlpbb", time_limit_s=600)
valves_only = optimize_debottlenecking(custom, budget=0.0, settings=settings)
budget_run = optimize_debottlenecking(custom, budget=4000.0, settings=settings, warm_start=valves_only)
current = simulate_existing_network(custom, custom.scenarios.hot_flow_increase_factor, settings=settings)
summary = T.table_costs({"current": current, "valves only": valves_only, "budget 4 kUSD/y": budget_run})
display(summary.round(2))
display(T.table_no_budget(current, valves_only).round(2))

# %%
fig, ax = plt.subplots(figsize=(6.5, 6))
F.plot_diameter_dotchart(custom, budget_run, ax=ax, label="B = 4 kUSD/y", title="Interventions with a 4 kUSD/y budget", show_pump=True)
plt.show()
budget_run.exchangers_df()[["k_kg_s", "T_hot_out_C", "T_hot_out_spec_C", "valve_head_loss_m", "penalty_USD_y"]].round(2)
