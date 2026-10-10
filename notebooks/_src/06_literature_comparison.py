# %% [markdown]
# # 06 · Comparison with a purely hydraulic approach - Table 12 and Fig. 11
#
# Section 3.7: Lee et al. (1997) only match **flow rates**. First, the cooler equations give the
# water flow rate each cooler would need to meet its set-point with the current hot stream flow
# rates (water supply temperature fixed at 32 °C). Then a purely hydraulic problem minimizes the
# sum of squared deviations between cooler flow rates and these targets, with the same budget as
# Case 1A. The thermal model is used afterwards only to *evaluate* the economic penalties.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from coolingnet import paper_case
from coolingnet.optimization import SolverSettings
from coolingnet.reporting import figures as F
from coolingnet.reporting import paper_reference as REF
from coolingnet.reporting import tables as T
from coolingnet.reporting.tables import flow_deviation
from coolingnet.workflow import PaperPipeline, PipelineConfig

RESULTS_DIR = Path("../results")
FORCE_RESOLVE = False

case = paper_case()
pipeline = PaperPipeline(case, PipelineConfig(results_dir=RESULTS_DIR, force=FORCE_RESOLVE, solver=SolverSettings(name="nlpbb", time_limit_s=900)))
sims = pipeline.run_simulations()
lit = pipeline.run_literature()
desired, hydraulic = lit["desired_flows"], lit["hydraulic_only"]
print("hydraulic-only run:", hydraulic.report["termination"], f"budget = {hydraulic.budget} USD/y")

# %% [markdown]
# ## Table 12

# %%
table12 = T.table_hydraulic_only(sims["current"], desired, hydraulic)
display(table12.round(3))
display(REF.compare(REF.TABLE12, table12.drop(index="Total")).round(3))

# %%
targets = {x["tag"]: x["k_kg_s"] for x in desired.exchangers}
dev_current = flow_deviation(sims["current"], targets)
dev_optimal = flow_deviation(hydraulic, targets)
pd.DataFrame(
    {
        "this work": [dev_current, dev_optimal, hydraulic.costs["cpen"] / 1e3],
        "paper": [REF.LEE_FLOW_DEVIATION["current_kg2_s2"], REF.LEE_FLOW_DEVIATION["optimal_kg2_s2"], REF.TABLE12_TOTALS["penalty"]],
    },
    index=["sum of squared flow deviations, current (kg2/s2)", "sum of squared flow deviations, optimal (kg2/s2)", "total penalty of the hydraulic solution (kUSD/y)"],
).round(1)

# %% [markdown]
# ## Fig. 11 - pipe diameters after the purely hydraulic optimization
#
# The purely hydraulic solution keeps the existing pump and reaches a lower flow-rate gap, but its
# economic performance is very poor: E-105 is almost starved of cooling water, which brings a huge
# penalty. Planning interventions requires the complete model (tower + network + coolers +
# economics).

# %%
fig, ax = plt.subplots(figsize=(6.5, 5.5))
F.plot_diameter_dotchart(case, hydraulic, ax=ax, label="Purely hydraulic (Case 1A budget)", title="Fig. 11")
fig.savefig("../figures/fig11_diameters_hydraulic_only.png", dpi=150, bbox_inches="tight")
print("pump:", hydraulic.pump_options(), "| pipes changed:", {str(e["id"]): e["diameter_in"] for e in hydraulic.edges if e.get("changed")})
print("paper:", REF.LEE_DESIGN)
