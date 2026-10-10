# Reproduction of Souza, Levy & Costa (2018) - cooling water system hydraulic debottlenecking
PY ?= .venv/bin/python
RESULTS ?= results

.PHONY: setup test test-fast run figures notebooks clean lint

setup:            ## create the virtual environment and install the package (needs `uv`)
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -e ".[notebooks,dev]"

lint:             ## static checks
	.venv/bin/ruff check src tests

test-fast:        ## unit tests (seconds)
	.venv/bin/pytest -q -m "not slow"

test:             ## all tests, including the optimization runs (minutes)
	.venv/bin/pytest -q

run:              ## solve every scenario of the paper (cached in $(RESULTS)/)
	.venv/bin/coolingnet -v run --results $(RESULTS)

run-quick:        ## same with coarse sweeps (~15 min)
	.venv/bin/coolingnet -v run --results $(RESULTS) --budget-steps 8 --penalty-steps 10

figures:          ## export every table (csv/md) and figure (png) from the cached results
	.venv/bin/coolingnet figures --results $(RESULTS) --out figures

notebooks:        ## regenerate the notebooks from notebooks/_src and execute them
	for f in notebooks/_src/*.py; do .venv/bin/jupytext --to ipynb --output "notebooks/$$(basename "$${f%.py}").ipynb" "$$f"; done
	cd notebooks && for nb in *.ipynb; do ../.venv/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=3600 "$$nb"; done

clean:
	rm -rf .pytest_cache .ruff_cache build dist
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
