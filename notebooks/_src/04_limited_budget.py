# %% [markdown]
# # 04 · Limited budget - Table 11, Figs. 5-8 and Video 1
#
# Section 3.5: the company has a limited yearly budget $B$ for interventions (Eq. 46). Three
# variants of Case 1 are solved (1A: 2.625, 1B: 4.125, 1C: 5.250 kUSD/y) and then a sweep over
# the budget shows how the optimal set of interventions evolves.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Image, display

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
unlimited = pipeline.run_unlimited()
budget_cases = pipeline.run_budget_cases()
for name, s in budget_cases.items():
    print(name, s.report["termination"], f"B = {s.budget / 1e3:.3f} kUSD/y", f"objective = {s.costs['total_cost'] / 1e3:.2f} kUSD/y", f"capital = {s.costs['capital'] / 1e3:.3f} kUSD/y")

# %% [markdown]
# ## Table 11 - optimization results with a finite budget

# %%
short = {k.replace("budget_", ""): v for k, v in budget_cases.items()}
display(T.table_budget_cases(short))
frames = {k: v.exchangers_df() for k, v in short.items()}
computed = pd.DataFrame(
    {
        **{f"Optimal flow {k} (kg/s)": f["k_kg_s"] for k, f in frames.items()},
        **{f"Valve head loss {k} (m)": f["valve_head_loss_m"] for k, f in frames.items()},
        **{f"Penalty {k} (kUSD/y)": f["penalty_USD_y"] / 1e3 for k, f in frames.items()},
    }
)
display(REF.compare(REF.TABLE11, computed).round(2))
display(T.table_costs(short).round(3))

# %% [markdown]
# ## Figs. 5 and 6 - interventions of Cases 1A and 1C
#
# Case 1A substitutes two pipes and keeps the pump; Case 1B buys the most powerful pump and
# changes no pipe; Case 1C combines the new pump with one pipe substitution.

# %%
fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
for ax, name in zip(axes, short, strict=True):
    F.plot_diameter_dotchart(case, short[name], ax=ax, label=f"Case {name}", title=f"Case {name}: B = {short[name].budget / 1e3:.3f} kUSD/y, pump {short[name].pump_options()['2']}")
fig.savefig("../figures/fig05_06_diameters_budget_cases.png", dpi=150, bbox_inches="tight")

# %% [markdown]
# ## Figs. 7 and 8 - budget sweep
#
# Beyond ~3 kUSD/y it becomes more interesting to buy the new pump and give up the additional
# pipe capacity (sudden drop of the penalty). The hatched region in Fig. 8 is above the budget
# line (infeasible capital cost).

# %%
sweep = pipeline.run_budget_sweep()
markers = {f"Case {k}": v for k, v in case.scenarios.budget_cases.items()}
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
F.plot_budget_costs(sweep, ax=axes[0], current_penalty=sims["current"].costs["cpen"], unlimited=unlimited["case1"], markers=markers, title="Fig. 7 - objective function vs. budget")
F.plot_budget_interventions(sweep, ax=axes[1], unlimited=unlimited["case1"], markers=markers, title="Fig. 8 - interventions vs. budget")
fig.savefig("../figures/fig07_08_budget_sweep.png", dpi=150, bbox_inches="tight")

# %%
pd.DataFrame(
    {
        "budget (kUSD/y)": [s.budget / 1e3 for s in sweep],
        "pipe (kUSD/y)": [s.costs["cpipe"] / 1e3 for s in sweep],
        "pump (kUSD/y)": [s.costs["cpump"] / 1e3 for s in sweep],
        "operating (kUSD/y)": [s.costs["cope"] / 1e3 for s in sweep],
        "penalty (kUSD/y)": [s.costs["cpen"] / 1e3 for s in sweep],
        "objective (kUSD/y)": [s.costs["total_cost"] / 1e3 for s in sweep],
        "pump option": ["/".join(s.pump_options().values()) for s in sweep],
        "pipes changed": [", ".join(f"{e['id']}:{e['diameter_in']:g}in" for e in s.edges if e["kind"] == "pipe" and e.get("changed")) for s in sweep],
        "status": [s.report["termination"] for s in sweep],
    }
).round(3)

# %% [markdown]
# ## Video 1 - evolution of the solution with the budget limit

# %%
gif = F.save_budget_animation(case, sweep, "../figures/video01_budget_animation.gif", fps=1.0)
display(Image(filename=str(gif)))
