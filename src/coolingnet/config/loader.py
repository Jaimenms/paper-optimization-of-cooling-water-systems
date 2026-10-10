"""Load / dump case studies from YAML."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml

from coolingnet.config.schema import CaseStudy


def paper_case_path() -> Path:
    """Path of the packaged configuration reproducing the paper's example."""
    return Path(str(resources.files("coolingnet").joinpath("data", "paper_case.yaml")))


def load_case(path: str | Path | None = None) -> CaseStudy:
    """Load a case study. Without arguments, the paper's case is returned."""
    p = Path(path) if path is not None else paper_case_path()
    with p.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return CaseStudy.model_validate(raw)


def paper_case() -> CaseStudy:
    return load_case(None)


def dump_case(case: CaseStudy, path: str | Path) -> Path:
    """Write a case study to YAML (useful as a starting point for a custom network)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = case.model_dump(mode="json")
    with p.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)
    return p
