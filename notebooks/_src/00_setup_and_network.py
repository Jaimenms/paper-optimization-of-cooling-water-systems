# %% [markdown]
# # 00 · Problem setup and network structure
#
# Reproduction of **Souza, Levy & Costa, "Optimization of cooling water system hydraulic
# debottlenecking", Applied Thermal Engineering 128 (2018) 1531-1542**
# ([doi:10.1016/j.applthermaleng.2017.09.089](https://doi.org/10.1016/j.applthermaleng.2017.09.089)).
#
# This notebook loads the case study (every number of Section 3.1 lives in a single YAML
# file), draws the network (Fig. 1), derives the hydraulic circuits (Table 1) and prints the
# problem data (Tables 2-7). The last section shows how to **change any parameter, including
# the network layout**.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from coolingnet import build_network, paper_case
from coolingnet.config import dump_case, paper_case_path
from coolingnet.reporting import plot_network
from coolingnet.reporting import tables as T

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)

case = paper_case()
print(case.name)
print("configuration file:", paper_case_path())

# %% [markdown]
# ## Fig. 1 - the cooling water distribution network
#
# Edges are pipes (numbered), one pump (edge 2) and five coolers (E-101 ... E-105). Node 1 is the
# cooling tower basin (water supply) and node 10 the tower top (water return). The network is a
# digraph described by its incidence matrix (Eq. 1); the hydraulic circuits (Eq. 3) are derived
# automatically as the unique supply-to-return path through each cooler.

# %%
fig, ax = plt.subplots(figsize=(11, 5))
plot_network(case, ax=ax, title="Fig. 1 - cooling water network (edge indices)")
fig.savefig("../figures/fig01_network.png", dpi=150, bbox_inches="tight")

# %% [markdown]
# ## Table 1 - hydraulic circuits

# %%
net = build_network(case.network)
T.table_circuits(case, net)

# %% [markdown]
# The incidence matrix $M_{t,k}$ (+1: edge enters node, -1: edge leaves node) and the circuit
# matrix $\Lambda_{l,k}$ used by the mechanical energy balances:

# %%
incidence = pd.DataFrame(net.incidence, index=pd.Index(net.nodes, name="node"), columns=[net.label(e) for e in net.edge_ids])
circuits = pd.DataFrame(net.circuit_matrix, index=pd.Index([c.index for c in net.circuits], name="circuit"), columns=incidence.columns)
display(incidence.replace(0, "·"))
display(circuits.replace(0, "·"))

# %% [markdown]
# ## Tables 2-7 - problem data

# %%
display(T.table_pipes(case))
display(T.table_pumps(case))
display(T.table_pump_cost_parameters(case))

# %%
display(T.table_thermal_tasks(case))
display(T.table_exchanger_design(case))
display(T.table_problem_parameters(case))

# %% [markdown]
# ## Configuring the problem
#
# Everything is data. Two ways to change the problem:
#
# 1. **Edit a YAML file.** `cases/paper_case.yaml` is an editable copy of the packaged paper
#    case (`src/coolingnet/data/paper_case.yaml`); export another copy with `dump_case` (or
#    `coolingnet export-config my_case.yaml` from a shell) and edit it. The `network.edges` list defines the
#    digraph: add/remove pipes and coolers, change lengths, existing diameters, the pump option,
#    node ids... `load_case("my_case.yaml")` validates everything (unique ids, catalogue
#    diameters, cooler data present for every cooler edge, single path per cooler); from a
#    shell, `coolingnet validate my_case.yaml` does the same check and prints the circuits.
# 2. **Programmatically**, with `case.with_updates(...)` / pydantic `model_copy`.
#
# Notebook `07_custom_network` walks through a complete example (a sixth cooler is added).

# %%
my_case_path = Path("../cases/my_case.yaml")
dump_case(case, my_case_path)
print(my_case_path.read_text()[:1200], "...")

# %%
# programmatic change: a stronger penalty and a cheaper energy price
alt = case.with_updates(
    heat_exchanger_defaults=case.heat_exchanger_defaults.model_copy(update={"penalty_factor_USD_per_C_y": 20000.0}),
    economics=case.economics.model_copy(update={"energy_cost_USD_kWh": 0.08}),
)
print("penalty factor:", alt.heat_exchanger("E-103").penalty_factor_USD_per_C_y, "USD/(y C)")
print("energy cost:", alt.economics.energy_cost_USD_kWh, "USD/kWh")

# %% [markdown]
# Structural errors are reported explicitly. For instance, a second pipe in parallel to the
# branch of E-101 creates two alternative paths, which the parallel-coolers model does not accept:

# %%
from coolingnet.config.schema import PipeEdge
from coolingnet.network import NetworkStructureError

bad_edges = list(case.network.edges) + [PipeEdge(id=99, tail=4, head=11, length_m=25, diameter_in=4)]
try:
    build_network(case.network.model_copy(update={"edges": bad_edges}))
except NetworkStructureError as err:
    print("NetworkStructureError:", err)
