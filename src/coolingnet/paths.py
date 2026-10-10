"""Locations of the repository data that is not packaged (``cases/``, ``data/reference/``).

The package is installed in editable mode from the repository (``uv sync``), so the repository
root is found by walking up from this file; ``COOLINGNET_ROOT`` overrides the search (useful when
the wheel is installed elsewhere).
"""

from __future__ import annotations

import os
from pathlib import Path

_MARKER = Path("data") / "reference" / "published_values.json"


def repo_root() -> Path:
    """Root of the repository (directory holding ``data/reference/published_values.json``)."""
    env = os.environ.get("COOLINGNET_ROOT")
    candidates = [Path(env)] if env else []
    candidates += list(Path(__file__).resolve().parents) + [Path.cwd(), *Path.cwd().parents]
    for c in candidates:
        if (c / _MARKER).is_file():
            return c
    raise FileNotFoundError(
        "repository root not found (no data/reference/published_values.json above "
        f"{Path(__file__).resolve()} nor above the current directory); set COOLINGNET_ROOT"
    )


def data_dir() -> Path:
    return repo_root() / "data"


def reference_dir() -> Path:
    """``data/reference``: published values and values parsed from the original GAMS listings."""
    return data_dir() / "reference"


def cases_dir() -> Path:
    """``cases/``: editable case files (the paper case and examples)."""
    return repo_root() / "cases"


def legacy_dir() -> Path:
    """``legacy/gams``: original GAMS sources, listings and logs (read-only)."""
    return repo_root() / "legacy" / "gams"
