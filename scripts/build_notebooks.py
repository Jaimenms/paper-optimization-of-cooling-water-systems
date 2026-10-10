"""Build and execute the reproduction notebooks.

The notebook sources are the jupytext percent-format scripts in ``notebooks/_src/``; this
script converts them to ``notebooks/NN_<slug>.ipynb`` and executes them in ``notebooks/``
(they read the result cache ``results/`` and write figures to ``figures/``)::

    uv run python scripts/build_notebooks.py                 # all notebooks, executed
    uv run python scripts/build_notebooks.py --no-execute    # convert only
    uv run python scripts/build_notebooks.py --only 01 05    # by number or name prefix
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import jupytext
import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "notebooks" / "_src"
OUT = ROOT / "notebooks"

KERNELSPEC = {"name": "python3", "display_name": "Python 3 (ipykernel)", "language": "python"}


def selected_sources(only: list[str] | None) -> list[Path]:
    sources = sorted(SRC.glob("*.py"))
    if not only:
        return sources
    chosen = [s for s in sources if any(s.stem == o or s.stem.startswith(o) for o in only)]
    missing = [o for o in only if not any(s.stem == o or s.stem.startswith(o) for s in sources)]
    if missing:
        raise SystemExit(
            f"no notebook source matches {missing}; available: {[s.stem for s in sources]}"
        )
    return chosen


def build(src: Path, *, execute: bool, timeout: int) -> Path:
    nb = jupytext.read(src)
    nb.metadata["kernelspec"] = KERNELSPEC
    nb.metadata.pop("jupytext", None)
    nb.metadata.setdefault("language_info", {"name": "python"})
    if execute:
        client = NotebookClient(
            nb,
            timeout=timeout,
            kernel_name="python3",
            resources={"metadata": {"path": str(OUT)}},
        )
        client.execute()
    out = OUT / f"{src.stem}.ipynb"
    nbformat.write(nb, out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--no-execute", action="store_true", help="convert the sources without executing them"
    )
    parser.add_argument(
        "--only",
        nargs="*",
        metavar="NAME",
        help="notebook numbers or name prefixes (e.g. 01 05_case)",
    )
    parser.add_argument(
        "--timeout", type=int, default=3600, help="per-cell timeout in seconds (default 3600)"
    )
    args = parser.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    failures = []
    for src in selected_sources(args.only):
        t0 = time.perf_counter()
        print(f"[{'exec' if not args.no_execute else 'conv'}] {src.name} ...", flush=True)
        try:
            out = build(src, execute=not args.no_execute, timeout=args.timeout)
        except Exception as exc:  # noqa: BLE001 - keep building the other notebooks
            failures.append((src.name, exc))
            print(
                f"       FAILED after {time.perf_counter() - t0:.0f} s: {type(exc).__name__}: {str(exc)[:400]}"
            )
            continue
        print(f"       -> {out.relative_to(ROOT)} ({time.perf_counter() - t0:.0f} s)")
    if failures:
        print(f"{len(failures)} notebook(s) failed: {', '.join(n for n, _ in failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
