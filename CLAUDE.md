# coolingnet — project guide

Python reimplementation of the MINLP of Souza, Levy & Costa, *Optimization of cooling water
system hydraulic debottlenecking*, Appl. Therm. Eng. 128 (2018) 1531–1542
(doi:10.1016/j.applthermaleng.2017.09.089). One of three repositories that follow the same
conventions: read `docs/conventions.md` first (layout, Makefile targets, CLI verbs, docs set).

## Commands
- `make setup` (`uv sync --all-extras`, Python 3.12 from `.python-version`).
- `make lint` / `make format` — ruff check (+ format --check) on `src tests scripts notebooks/_src`.
- `make test` — fast tests (`-m "not slow"`, seconds); `make test-all` adds the solver runs (minutes).
- `make run` — every scenario of the paper into `results/` (~30 min with the default `nlpbb`
  solver; `make run-quick` uses coarse sweeps). Runs are cached by name; nothing is re-solved
  unless `--force`.
- `make eval` — compare `results/` with the published values → `results/eval/report.md` + CSVs.
- `make figures` — Tables 1–12 (csv/md) and Figs. 1–11 + Video 1 (png/gif) into `figures/`.
- `make notebooks` — `scripts/build_notebooks.py`: jupytext sources `notebooks/_src/*.py` →
  executed `notebooks/*.ipynb` (`--no-execute`, `--only 03`).
- CLI: `uv run coolingnet info | validate <case> | run [<case>] [--out] | eval [--out] | figures [--out]`
  (+ `simulate`, `show-network`, `export-config`, `solvers`).

## Layout
- `src/coolingnet/` — `config` (pydantic schema + YAML loader, packaged `data/paper_case.yaml`),
  `network` (digraph, incidence/circuit matrices), `physics` (hydraulics, P-NTU coolers, Merkel
  tower; backend-agnostic), `economics`, `simulation` (NumPy cross-check), `optimization`
  (Pyomo model, CasADi bridge, `nlpbb` branch-and-bound, solvers, `Solution`), `workflow`
  (`ResultStore` JSON cache + `PaperPipeline`), `reporting` (tables, figures, `paper_reference`,
  `evaluation`), `cli.py`, `paths.py` (repo-relative data).
- `cases/` editable case files (`paper_case.yaml` must equal the packaged default).
- `data/reference/` published values (`published_values.json`) and values parsed from the
  original GAMS listings (`d4_*.json`, via `scripts/parse_gams_lst.py`).
- `legacy/gams/` original GAMS sources, listings and logs that produced the published results
  (read-only; the user's own code). Paper PDFs, drafts and reviews are **not** in the repository.
- `docs/` formulation.md (equations ↔ code), architecture.md, reproduction.md, errata.md,
  conventions.md, `pt/` (Portuguese working notes).

## Conventions and exceptions
- SI units internally (m, kg/s, W, USD/y); nominal diameters in inches; tables in the paper's
  units (kUSD/y, °C). The packaged case keeps the values of the original GAMS code where the
  paper text differs (Merkel abscissa 0.7, see `docs/errata.md`); paper variants are options.
- **`results/` and `figures/` are committed on purpose** (a full `make run` takes ~30 min); the
  notebooks, `make eval` and `make figures` read the cache. Only `results/eval/` is ignored.
  This is the allowed exception of `docs/conventions.md`.
- Notebooks are generated: edit `notebooks/_src/*.py`, never the `.ipynb` files.
- Keep ruff clean (line length 100, E501 ignored for formulas) and the fast tests green.
