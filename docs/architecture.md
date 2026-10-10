# Architecture

```
src/coolingnet/
├── config/        pydantic schema of a case study + YAML loader (data, no physics)
│   └── data/paper_case.yaml   every number of the paper's example (packaged default)
├── network/       digraph → incidence matrix, hydraulic circuits (Table 1), validation
├── physics/       hydraulics, heat exchangers (P-NTU), cooling tower (Merkel) — backend agnostic
├── economics/     cost correlations (pipes, pumps, operation, annualization)
├── simulation/    NumPy/SciPy simulation of a fixed design (independent cross-check)
├── optimization/
│   ├── spec.py          ProblemSpec / Design: which variant of the MINLP to build
│   ├── model.py         Pyomo model (Eqs. 1-55), scaling suffix, initialization helpers
│   ├── casadi_bridge.py Pyomo → CasADi translation; Bonmin / IPOPT solve
│   ├── nlpbb.py         NLP-based branch-and-bound (IPOPT nodes, SOS1 branching) - default MINLP solver
│   ├── solvers.py       SolverSettings / SolveReport; back-ends bonmin, ipopt, scip, pyomo shell
│   ├── isolation.py     child-process execution of a solve (crash containment, retries)
│   ├── results.py       Solution: plain-data snapshot (JSON, pandas)
│   └── problems.py      high-level entry points (Sections 3.2-3.7)
├── workflow/      ResultStore (JSON cache) + PaperPipeline (all scenarios, resumable)
├── reporting/     tables (Tables 1-12), figures (Figs. 1-11, Video 1), paper_reference
│                  (published values), evaluation (`coolingnet eval`), export (`figures`)
├── paths.py       repository-relative data (cases/, data/reference/, legacy/gams/)
└── cli.py         `coolingnet` command line (info, validate, run, eval, figures, ...)
cases/             editable case files (paper_case.yaml = packaged default, examples)
data/reference/    published values (JSON) and values parsed from the original GAMS listings
notebooks/         executed notebooks NN_<slug>.ipynb (sources in notebooks/_src, jupytext percent)
scripts/           build_notebooks.py, parse_gams_lst.py
results/           cached solutions (one JSON per run; sweeps in sub-directories) - committed
figures/           exported figures/tables - committed
legacy/gams/       original GAMS sources, listings and logs (read-only)
tests/             pytest suite (fast unit/regression tests + slow optimization tests)
docs/              formulation, architecture, reproduction, errata, conventions, pt/
```

## Design principles

* **Data-driven**: topology, catalogues and parameters are data (`CaseStudy`), validated by
  pydantic; nothing about the example network is hard-coded. The packaged
  `paper_case.yaml` is the reference; `cases/paper_case.yaml` is its editable copy.
* **One physics, two engines**: the same functions build Pyomo expressions and evaluate NumPy
  arrays (`physics.backend.MathOps`), so the simulator validates the optimization model.
* **Original-code behaviour by default**: where the paper text and the GAMS code differ
  (Merkel abscissa, see `errata.md`) the configuration keeps the code values that reproduce the
  published tables; the text variants are options (`cooling_tower.quadrature_points`).
* **Reproducible and resumable**: every run is cached as JSON by name in `results/`
  (`ResultStore`); the notebooks, `eval` and `figures` read the cache and the notebooks can
  re-solve on demand (`FORCE_RESOLVE = True`). Because a full `make run` takes about half an
  hour, `results/` and `figures/` are committed.
* **Solver-agnostic**: the Pyomo model is translated to CasADi (own branch-and-bound `nlpbb`,
  Bonmin, IPOPT) or written as an `.nl` file (SCIP, external executables); every
  branch-and-bound runs in a child process so that a solver crash never aborts a sweep.
* **Published values as data**: `data/reference/published_values.json` feeds
  `reporting.paper_reference` (used by the notebooks) and `reporting.evaluation`
  (`coolingnet eval`, markdown + CSV report with the deviations).

## Data flow

```
cases/*.yaml ──load_case──▶ CaseStudy ──build_network──▶ Network (incidence, circuits)
                                 │                            │
                                 ├── simulation.simulate_design (NumPy)   ──▶ SimulationResult
                                 └── optimization.build_model (Pyomo) ──solve──▶ Solution ──▶ results/*.json
                                                                                     │
                       reporting.tables / figures / evaluation ◀── workflow.ResultStore ◀──┘
                                 │
                       figures/*.csv|md|png|gif, results/eval/report.md, notebooks/*.ipynb
```
