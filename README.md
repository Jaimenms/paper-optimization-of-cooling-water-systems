# coolingnet — optimization of cooling water system hydraulic debottlenecking

Python reimplementation of

> J.N.M. Souza, A.L.L. Levy, A.L.H. Costa, **Optimization of cooling water system hydraulic
> debottlenecking**, *Applied Thermal Engineering* 128 (2018) 1531–1542.
> https://doi.org/10.1016/j.applthermaleng.2017.09.089

The original work was developed in GAMS (SBB + CONOPT) with R post-processing
(`docs/raw/`). This repository rebuilds the MINLP in Python/Pyomo, solves it with
pip-installable solvers (an NLP-based branch-and-bound with IPOPT nodes, Bonmin and IPOPT
through CasADi, SCIP through PySCIPOpt) and reproduces every table, figure, diagram and
animation of the paper in Jupyter notebooks. The network
topology and **every** parameter are configuration data, so other cooling water systems can be
studied with the same code.

## Quick start

```bash
# requires Python 3.11-3.13 and uv (https://docs.astral.sh/uv/)
make setup                      # creates .venv and installs coolingnet with notebook/dev extras
.venv/bin/coolingnet solvers    # nlpbb / bonmin / ipopt / scip should be available
.venv/bin/coolingnet show-network
.venv/bin/coolingnet simulate --hot-flow-factor 1.2      # Table 8, current condition
make run                        # all scenarios of the paper (~30 min with the default solver)
make figures                    # figures/ and tables from the cached results
.venv/bin/jupyter lab notebooks # open the notebooks
```

Results are cached as JSON in `results/` (one file per run, sweeps in sub-directories); the
notebooks read the cache and can re-solve anything with `FORCE_RESOLVE = True`.

## Notebooks

| Notebook | Paper items |
|---|---|
| `00_setup_and_network` | Fig. 1, Tables 1–7, how to configure parameters and the network layout |
| `01_water_shortage` | Table 8 (initial and current conditions), NumPy vs. Pyomo/IPOPT cross-check |
| `02_no_available_budget` | Table 9, SciPy cross-check of the valve-only optimum |
| `03_unlimited_budget` | Table 10, Figs. 2–3 (diameters), Fig. 4 (penalty factor sweep) |
| `04_limited_budget` | Table 11, Figs. 5–8, Video 1 (budget sweep animation) |
| `05_case_comparison` | Figs. 9–10 |
| `06_literature_comparison` | Table 12, Fig. 11 (purely hydraulic approach of Lee et al.) |
| `07_custom_network` | a sixth cooler is added; parameters changed; simulation and optimization |

Notebook sources live in `notebooks/_src/*.py` (jupytext percent format); `make notebooks`
regenerates and executes them.

## Configuring a case

All data of the example (`src/coolingnet/data/paper_case.yaml`) can be exported, edited and
loaded back:

```bash
.venv/bin/coolingnet export-config configs/my_case.yaml
# edit network.edges (pipes, pump, coolers, node ids, lengths, existing diameters),
# heat_exchangers, pipes.catalogue, pumps.options, cooling_tower, economics, scenarios ...
.venv/bin/coolingnet run --config configs/my_case.yaml --results results_my_case
```

or in Python:

```python
from coolingnet import load_case
from coolingnet.optimization.problems import optimize_debottlenecking, simulate_existing_network

case = load_case("configs/my_case.yaml")
current = simulate_existing_network(case, hot_flow_factor=1.2)
best = optimize_debottlenecking(case, budget=4000.0, penalty_factor=20000.0)
print(best.costs, best.pipe_diameters(), best.pump_options())
```

The digraph is validated when the network is built: unique ids, catalogue diameters, cooler data
for every cooler edge, supply/return nodes, connectivity and a single hydraulic circuit per
cooler (coolers in parallel, as in the paper).

## What is reproduced

* Table 8 (simulation) — exact to the printed precision, with two independent engines.
* Table 9 (valves only) — exact.
* Table 10 / Figs. 2–3 (unlimited budget) — Case 1 exact (same pipes, pump, flows, penalties);
  Case 2 within 0.01 % of the published objective (slightly better local optimum).
* Table 11 / Figs. 5–6 (finite budget) — Cases 1A and 1C exact; Case 1B 0.02 % better than
  published (the pump substitution plus one small pipe instead of the pump alone).
* Figs. 7–8 / Video 1 (budget sweep), Fig. 4 (penalty sweep), Figs. 9–10, Table 12 / Fig. 11
  (Lee et al. comparison) — see the notebooks for a side-by-side comparison with the published
  values (`coolingnet.reporting.paper_reference`).

The MINLP is non-convex: like the SBB runs of the paper, the NLP-based branch-and-bound returns
local optima (Case 2 ends 0.01 % below the published value with a slightly different pipe set). Two
discrepancies between the paper text and the original GAMS code, and one physical safeguard added
to the cooling tower model (positive enthalpy driving force, which removes a spurious root of the
regularized Merkel integral), are documented in [`docs/model.md`](docs/model.md).

## Documents

* [`docs/model.md`](docs/model.md) — equation ↔ code map, solution strategy.
* [`docs/architecture.md`](docs/architecture.md) — package layout and design principles.
* [`docs/achados.md`](docs/achados.md) — the three findings of the port (in Portuguese).
* [`docs/errata.md`](docs/errata.md) — errata of the paper with location and quantified impact
  (in Portuguese).

## Layout

```
src/coolingnet/   package (config, network, physics, economics, simulation, optimization, workflow, reporting, cli)
notebooks/        reproduction notebooks (+ _src/ jupytext sources)
results/          cached runs (JSON)        figures/   exported figures and tables
tests/            pytest suite              tools/     GAMS listing parser used during the port
docs/raw/         original paper, GAMS sources, R scripts
```

## Tests

```bash
make test-fast    # unit tests: network, physics, economics, simulator vs. Table 8, model build
make test         # + slow tests that re-solve Tables 8-10
```

## License

MIT for the code. The paper and the original GAMS/R material in `docs/raw/` keep their own
copyright.
