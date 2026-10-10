# %% [markdown]
# # 02 · No available budget - Table 9
#
# Section 3.3: without money for pipe or pump substitutions ($B = 0$ in Eq. 46), the only
# degrees of freedom are the valve head losses of the five hydraulic circuits, which redistribute
# the cooling water towards the coolers with the highest penalties.

# %%
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from coolingnet import paper_case
from coolingnet.optimization import SolverSettings
from coolingnet.reporting import paper_reference as REF
from coolingnet.reporting import tables as T
from coolingnet.simulation import simulate_design
from coolingnet.workflow import PaperPipeline, PipelineConfig

RESULTS_DIR = Path("../results")
FORCE_RESOLVE = False

case = paper_case()
pipeline = PaperPipeline(case, PipelineConfig(results_dir=RESULTS_DIR, force=FORCE_RESOLVE, solver=SolverSettings(name="nlpbb", time_limit_s=600)))
sims = pipeline.run_simulations()
no_budget = pipeline.run_no_budget()
print(no_budget.report)

# %% [markdown]
# ## Table 9 - optimization results with no available budget

# %%
table9 = T.table_no_budget(sims["current"], no_budget)
display(table9.round(2))
display(REF.compare(REF.TABLE9, table9.drop(index="Total")).round(2))

# %%
cur, opt = sims["current"].costs, no_budget.costs
summary = pd.DataFrame(
    {
        "current condition": [cur["cpen"] / 1e3, cur["cope"] / 1e3, (cur["cpen"] + cur["cope"]) / 1e3],
        "valve manipulation": [opt["cpen"] / 1e3, opt["cope"] / 1e3, (opt["cpen"] + opt["cope"]) / 1e3],
        "paper": [REF.NO_BUDGET_TEXT["penalty_before"], REF.NO_BUDGET_TEXT["operating_before"], None],
        "paper (after)": [REF.NO_BUDGET_TEXT["penalty_after"], REF.NO_BUDGET_TEXT["operating_after"], None],
    },
    index=["penalty (kUSD/y)", "operating cost (kUSD/y)", "total (kUSD/y)"],
)
display(summary.round(2))
reduction = (1 - (opt["cpen"] + opt["cope"]) / (cur["cpen"] + cur["cope"])) * 100
print(f"total cost reduction: {reduction:.2f} %  (paper: {REF.NO_BUDGET_TEXT['total_reduction_pct']} %)")

# %% [markdown]
# ## Independent cross-check with the NumPy simulator
#
# With the design fixed, the problem has only five continuous unknowns (the valve head losses).
# Minimizing operating + penalty cost over them with SciPy (SLSQP) on top of the NumPy simulator
# must give the same optimum as the Pyomo/IPOPT solution.

# %%
pen = case.heat_exchanger_defaults.penalty_factor_USD_per_C_y
factor = case.scenarios.hot_flow_increase_factor


def total_cost(valves: np.ndarray) -> float:
    r = simulate_design(case, valve_head_losses_m={i + 1: max(v, 0.0) for i, v in enumerate(valves)}, hot_flow_factor=factor)
    return r.total_cost_USD_y


x0 = np.zeros(5)
res = minimize(total_cost, x0, method="SLSQP", bounds=[(0, 10)] * 5, options={"ftol": 1e-10, "maxiter": 300})
print("SLSQP valve head losses (m):", np.round(res.x, 2), " total cost:", round(res.fun / 1e3, 2), "kUSD/y")
print("Pyomo/IPOPT valve head losses (m):", np.round(no_budget.circuits_df()["valve_head_loss_m"].values, 2), " total cost:", round(opt["total_cost"] / 1e3, 2), "kUSD/y")
