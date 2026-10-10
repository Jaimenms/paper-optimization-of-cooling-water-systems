# %% [markdown]
# # 05 · Comparison of the different cases - Figs. 9 and 10
#
# Section 3.6: more available funds allow more interventions, lower objective function values
# and larger penalty reductions (relative to the current condition, 73.71 kUSD/y).

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from coolingnet import paper_case
from coolingnet.optimization import SolverSettings
from coolingnet.reporting import figures as F
from coolingnet.reporting import paper_reference as REF
from coolingnet.reporting import tables as T
from coolingnet.workflow import PaperPipeline, PipelineConfig

RESULTS_DIR = Path("../results")
FORCE_RESOLVE = False

case = paper_case()
pipeline = PaperPipeline(case, PipelineConfig(results_dir=RESULTS_DIR, force=FORCE_RESOLVE, solver=SolverSettings(name="nlpbb", time_limit_s=900)))
sims = pipeline.run_simulations()
comparison = {"No Budget": pipeline.run_no_budget()}
comparison.update({f"Case {k.replace('budget_', '')}": v for k, v in pipeline.run_budget_cases().items()})
comparison["Case 1"] = pipeline.run_unlimited()["case1"]

# %%
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
F.plot_comparison_bars(comparison, quantity="objective", ax=axes[0], title="Fig. 9 - objective function values")
F.plot_comparison_bars(comparison, quantity="penalty_reduction", reference_penalty=sims["current"].costs["cpen"], ax=axes[1], title="Fig. 10 - penalty reduction")
fig.savefig("../figures/fig09_10_comparison.png", dpi=150, bbox_inches="tight")

# %%
ref_pen = sims["current"].costs["cpen"]
pd.DataFrame(
    {
        "objective (kUSD/y) [paper]": pd.Series(REF.FIG9_OBJECTIVE_KUSD),
        "objective (kUSD/y) [this work]": pd.Series({k: v.costs["total_cost"] / 1e3 for k, v in comparison.items()}),
        "penalty reduction (%) [paper]": pd.Series(REF.FIG10_PENALTY_REDUCTION_PCT),
        "penalty reduction (%) [this work]": pd.Series({k: (ref_pen - v.costs["cpen"]) / ref_pen * 100 for k, v in comparison.items()}),
    }
).round(2)

# %%
T.table_costs(comparison).round(3)
