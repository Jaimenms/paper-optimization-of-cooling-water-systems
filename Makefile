# coolingnet - series conventions: see docs/conventions.md
.PHONY: setup lint format test test-all run run-quick eval figures notebooks clean

RESULTS ?= results

setup:            ## create .venv with uv (Python 3.12) and install the package with all extras
	uv sync --all-extras

lint:             ## static checks
	uv run ruff check src tests scripts notebooks/_src
	uv run ruff format --check src tests scripts

format:           ## format the code
	uv run ruff format src tests scripts
	uv run ruff check --fix src tests scripts notebooks/_src

test:             ## fast tests (seconds)
	uv run pytest -q -m "not slow"

test-all:         ## all tests, including the slow optimization runs (minutes)
	uv run pytest -q

run:              ## solve every scenario of the paper and write $(RESULTS)/ (~30 min, cached)
	uv run coolingnet -v run --out $(RESULTS)

run-quick:        ## same with coarse sweeps (~15 min)
	uv run coolingnet -v run --out $(RESULTS) --budget-steps 8 --penalty-steps 10

eval:             ## compare the cached results with the published tables and write $(RESULTS)/eval/
	uv run coolingnet eval --results $(RESULTS) --out $(RESULTS)/eval

figures:          ## export every table (csv/md) and figure (png) of the paper to figures/
	uv run coolingnet figures --results $(RESULTS) --out figures

notebooks:        ## regenerate the notebooks from notebooks/_src and execute them
	uv run python scripts/build_notebooks.py

clean:            ## remove caches and build artefacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
