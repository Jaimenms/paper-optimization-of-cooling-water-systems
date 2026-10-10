# Architecture

```
src/coolingnet/
├── config/        pydantic schema of a case study + YAML loader (data, no physics)
│   └── data/paper_case.yaml   every number of the paper's example
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
├── reporting/     Tables 1-12, Figs. 1-11, Video 1, paper reference values
└── cli.py         `coolingnet` command line
notebooks/         reproduction notebooks (sources in notebooks/_src, jupytext percent format)
results/           cached solutions (one JSON per run; sweeps in sub-directories)
figures/           exported figures/tables
tests/             pytest suite (fast unit tests + slow optimization tests)
tools/             helpers used while porting (GAMS listing parser)
docs/raw/          original material (paper, GAMS sources, R scripts)
```

Design principles

* **Data-driven**: topology, catalogues and parameters are data (`CaseStudy`), validated by
  pydantic; nothing about the example network is hard-coded.
* **One physics, two engines**: the same functions build Pyomo expressions and evaluate NumPy
  arrays (`physics.backend.MathOps`), so the simulator validates the optimization model.
* **Reproducible and resumable**: every run is cached as JSON by name; notebooks read the cache
  and can re-solve on demand (`FORCE_RESOLVE = True`).
* **Solver-agnostic**: the Pyomo model is translated to CasADi (own branch-and-bound, Bonmin,
  IPOPT) or written as an `.nl` file (SCIP, external executables).
