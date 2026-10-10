"""Command line verbs shared by the series: info, validate, run, eval, figures (+ extras)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from coolingnet import __version__
from coolingnet.cli import app
from coolingnet.paths import cases_dir, repo_root

runner = CliRunner()


def _run(*args: str):
    return runner.invoke(app, list(args), env={"COLUMNS": "200"})


def test_help_lists_the_series_verbs():
    r = _run("--help")
    assert r.exit_code == 0
    for verb in (
        "info",
        "validate",
        "run",
        "eval",
        "figures",
        "simulate",
        "show-network",
        "export-config",
        "solvers",
    ):
        assert verb in r.output


def test_info_prints_reference_cases_and_version():
    r = _run("info")
    assert r.exit_code == 0, r.output
    assert __version__ in r.output
    assert "Souza" in r.output and "10.1016/j.applthermaleng.2017.09.089" in r.output
    assert "paper_case.yaml" in r.output
    assert "nlpbb" in r.output


def test_validate_accepts_the_paper_case():
    r = _run("validate", str(cases_dir() / "paper_case.yaml"))
    assert r.exit_code == 0, r.output
    assert "is valid" in r.output
    assert "20 nodes" in r.output and "23 edges" in r.output
    assert "E-105" in r.output  # circuit table


def test_validate_rejects_a_broken_case(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        (cases_dir() / "paper_case.yaml").read_text().replace('option: "1"', 'option: "9"')
    )
    r = _run("validate", str(bad))
    assert r.exit_code == 1
    assert "invalid case file" in r.output and "not in the catalogue" in r.output


def test_run_accepts_positional_case_and_out_alias():
    r = _run("run", "--help")
    assert r.exit_code == 0
    assert "--out" in r.output and "--results" in r.output and "CASE" in r.output.upper()


def test_eval_on_the_committed_cache(tmp_path: Path):
    out = tmp_path / "eval"
    r = _run("eval", "--results", str(repo_root() / "results"), "--out", str(out))
    assert r.exit_code == 0, r.output
    assert (out / "report.md").exists() and (out / "summary.csv").exists()
    assert (out / "table08.csv").exists() and (out / "designs.csv").exists()
    assert "Table 8" in r.output and "reproduced" in r.output
    report = (out / "report.md").read_text()
    assert "## Summary" in report and "Table 12" in report and "GAMS" in report


def test_simulate_current_condition():
    r = _run("simulate", "--hot-flow-factor", "1.2")
    assert r.exit_code == 0, r.output
    assert "E-103" in r.output and "converged=True" in r.output


def test_export_config_round_trip(tmp_path: Path):
    target = tmp_path / "case.yaml"
    r = _run("export-config", str(target))
    assert r.exit_code == 0, r.output
    assert target.exists()
    r = _run("validate", str(target))
    assert r.exit_code == 0, r.output


@pytest.mark.parametrize("verb", ["show-network", "figures", "eval"])
def test_rejects_conflicting_case_arguments(verb, tmp_path: Path):
    case = cases_dir() / "paper_case.yaml"
    other = cases_dir() / "example_six_coolers.yaml"
    r = _run(verb, str(case), "--config", str(other), "--out", str(tmp_path))
    assert r.exit_code != 0
