# coolingnet — optimization of cooling water system hydraulic debottlenecking

Python reimplementation of

> J.N.M. Souza, A.L.L. Levy, A.L.H. Costa, **Optimization of cooling water system hydraulic
> debottlenecking**, *Applied Thermal Engineering* 128 (2018) 1531–1542.
> https://doi.org/10.1016/j.applthermaleng.2017.09.089

The paper proposes an MINLP that chooses, under a budget limit, which pipes to replace, which
pump to install and how to throttle the hydraulic circuits of an existing cooling water
system whose coolers no longer meet their set-points, modelling the network hydraulics, the
coolers (P-NTU), the cooling tower (Merkel) and the costs simultaneously. The original work was
developed in GAMS (SBB + CONOPT; the sources, listings and logs are in `legacy/gams/`). This
repository rebuilds the model in Python/Pyomo, solves it with pip-installable solvers (an
NLP-based branch-and-bound with IPOPT nodes, Bonmin and IPOPT through CasADi, SCIP through
PySCIPOpt) and reproduces every table, figure and the animation of the paper. The network
topology and every parameter are configuration data, so other cooling water systems can be
studied with the same code.

One of three repositories that share the same layout, commands and documents
([`docs/conventions.md`](docs/conventions.md)).

## What is reproduced

| Paper item | Status |
|---|---|
| Fig. 1, Tables 1–7 (network, circuits, data) | reproduced from the case file |
| Table 8 (existing network, water shortage) | reproduced to the printed precision, two independent engines |
| Table 9 (no available budget, valves only) | reproduced |
| Table 10 / Figs. 2–3 (unlimited budget) | Case 1 reproduced (pump 4, pipes 5–6 → 8 in); Case 2 objective 0.01 % lower, different local optimum |
| Fig. 4 (penalty factor sweep) | reproduced qualitatively (no printed values) |
| Table 11 / Figs. 5–6 (finite budget) | 1A and 1C reproduced (1C with the interchangeable pipe 6 instead of 5); 1B objective 0.02 % lower |
| Figs. 7–8, Video 1 (budget sweep) | reproduced qualitatively; GAMS sweep point within 0.005 % |
| Figs. 9–10 (comparison of the cases) | reproduced (Case 1B as above) |
| Table 12 / Fig. 11 (purely hydraulic approach) | desired flows reproduced; optimum with a lower flow-deviation objective, E-105 differs |

Details, the discrepancies that are not errors of the paper and the notes on the original code
are in [`docs/reproduction.md`](docs/reproduction.md); `make eval` regenerates the comparison
(`results/eval/report.md`). Five errata of the paper (one changes the published numbers: the
Merkel quadrature abscissa 0.9 printed vs 0.7 used) are in [`docs/errata.md`](docs/errata.md).

## Quick start

```bash
# requires Python 3.12 and uv (https://docs.astral.sh/uv/)
make setup        # uv sync --all-extras: creates .venv with the package, notebook and dev extras
make test         # fast tests (seconds); make test-all adds the solver runs (minutes)
make eval         # compare the cached results with the published values -> results/eval/
make figures      # export Tables 1-12 (csv/md) and Figs. 1-11 + Video 1 (png/gif) -> figures/
make notebooks    # regenerate and execute notebooks/*.ipynb from notebooks/_src/*.py
make run          # re-solve every scenario of the paper (~30 min, cached in results/)
make lint         # ruff
```

`results/` (JSON cache of every run) and `figures/` are committed on purpose: a full
`make run` takes about half an hour, and everything else (tests, notebooks, `eval`, `figures`)
reads the cache. This is the allowed exception of the series conventions.

Command line (`uv run coolingnet --help`):

```bash
uv run coolingnet info                              # paper reference, cases, version, solvers, cache
uv run coolingnet validate cases/paper_case.yaml    # schema, catalogues, topology, circuits (Table 1)
uv run coolingnet run [cases/my_case.yaml] --out results   # every scenario of the paper (cached)
uv run coolingnet eval --out results/eval           # deviations from the published tables (md + csv)
uv run coolingnet figures --out figures             # figures and tables from the cache
uv run coolingnet simulate --hot-flow-factor 1.2    # Table 8, current condition (NumPy)
uv run coolingnet show-network | solvers | export-config my_case.yaml
```

Python:

```python
from coolingnet import load_case
from coolingnet.optimization.problems import optimize_debottlenecking, simulate_existing_network

case = load_case()                                   # the paper case (or load_case("cases/my_case.yaml"))
current = simulate_existing_network(case, hot_flow_factor=1.2)      # Table 8
best = optimize_debottlenecking(case, budget=4000.0, penalty_factor=12500.0)
print(best.costs, best.pipe_diameters(), best.pump_options())
```

## Notebooks

Executed notebooks in `notebooks/` (sources in `notebooks/_src/*.py`, jupytext percent format;
`make notebooks` rebuilds them). Every table and figure cell names the paper item and shows the
published values side by side.

| Notebook | Paper items |
|---|---|
| `00_setup_and_network` | Fig. 1, Tables 1–7; how to configure parameters and the network layout |
| `01_water_shortage` | Table 8 (initial and current conditions), NumPy vs Pyomo/IPOPT cross-check, effect of the Merkel abscissa |
| `02_no_available_budget` | Table 9, Section 3.3 text, SciPy cross-check of the valve-only optimum |
| `03_unlimited_budget` | Table 10, Figs. 2–3 (diameters), Fig. 4 (penalty factor sweep) |
| `04_limited_budget` | Table 11, Figs. 5–8, Video 1 (budget sweep animation) |
| `05_case_comparison` | Figs. 9–10 |
| `06_literature_comparison` | Table 12, Fig. 11 (purely hydraulic approach of Lee et al.) |
| `07_custom_network` | a sixth cooler is added, parameters changed; simulation and optimization |

## Configuring a case

`cases/paper_case.yaml` is an editable copy of the packaged paper case
(`src/coolingnet/data/paper_case.yaml`, the default of `load_case()` and of the CLI); see
[`cases/README.md`](cases/README.md). Copy it (or `coolingnet export-config my_case.yaml`),
edit `network.edges` (pipes, pump, coolers, node ids, lengths, existing diameters),
`heat_exchangers`, `pipes.catalogue`, `pumps.options`, `cooling_tower`, `economics`,
`scenarios`, and run:

```bash
uv run coolingnet validate cases/my_case.yaml
uv run coolingnet run cases/my_case.yaml --out results_my_case
uv run coolingnet figures cases/my_case.yaml --results results_my_case --out figures_my_case
```

The digraph is validated when the network is built: unique ids, catalogue diameters, cooler
data for every cooler edge, supply/return nodes, connectivity and a single hydraulic circuit per
cooler (coolers in parallel, as in the paper). Notebook `07` builds a six-cooler network in
Python.

## Layout

```
README.md  CITATION.cff  LICENSE  CLAUDE.md  Makefile  pyproject.toml  uv.lock  .python-version
src/coolingnet/   config, network, physics, economics, simulation, optimization, workflow, reporting, cli
cases/            paper_case.yaml (editable copy of the packaged case), example_six_coolers.yaml
data/reference/   published_values.json (Tables 8-12, Figs. 9-10) and d4_*.json (original GAMS listings)
notebooks/        executed notebooks NN_<slug>.ipynb (+ _src/ jupytext sources)
scripts/          build_notebooks.py, parse_gams_lst.py
tests/            pytest suite (fast by default; solver runs carry the `slow` marker)
docs/             formulation.md, architecture.md, reproduction.md, errata.md, conventions.md, pt/
legacy/gams/      original GAMS sources, listings and logs (read-only)
results/          cached runs (JSON, committed) and results/eval/ (make eval)
figures/          figures and tables exported by make figures (committed)
```

## Documents

* [`docs/formulation.md`](docs/formulation.md) — equation ↔ code map, solution strategy.
* [`docs/architecture.md`](docs/architecture.md) — package layout and design decisions.
* [`docs/reproduction.md`](docs/reproduction.md) — status per table/figure, discrepancies that
  are not paper errors, notes on the original GAMS code.
* [`docs/errata.md`](docs/errata.md) — formal errata of the paper (location, published text,
  correction, impact).
* [`docs/conventions.md`](docs/conventions.md) — conventions of the three-repository series.
* `docs/pt/` — Portuguese working notes (`errata.md`, `achados.md`).

## Resumo em português

`coolingnet` reimplementa em Python o modelo MINLP do artigo *Optimization of cooling water
system hydraulic debottlenecking* (Souza, Levy & Costa, Applied Thermal Engineering 128, 2018):
dada uma rede de água de resfriamento existente cujos trocadores já não atendem aos set-points
(aumento das vazões dos fluidos quentes), o modelo escolhe, sob um orçamento limitado, quais
tubulações substituir, qual bomba instalar e como estrangular os circuitos hidráulicos,
acoplando hidráulica da rede, trocadores (P-NTU), torre de resfriamento (Merkel) e custos. O
código original, em GAMS (SBB + CONOPT), está em `legacy/gams/`; a reimplementação usa
Pyomo com um branch-and-bound próprio baseado em IPOPT (Bonmin, IPOPT e SCIP como
alternativas) e reproduz todas as tabelas, figuras e a animação do artigo nos notebooks de
`notebooks/`. Todos os parâmetros, inclusive a topologia da rede, são configuráveis em YAML
(`cases/`). O estado da reprodução está em `docs/reproduction.md`; a errata do artigo (a
abscissa de quadratura de Merkel impressa como 0,9 foi calculada com 0,7, entre outros itens)
está em `docs/errata.md`, com as versões em português em `docs/pt/`.

## License

MIT for the code (see `LICENSE`). The paper keeps its own copyright; the original GAMS material
in `legacy/gams/` is the authors' own code.
