"""Run a solve in a child process so that a solver crash cannot kill the caller.

Bonmin (through CasADi) occasionally aborts at the C++ level on this non-convex MINLP
("Uncaught error in Bonmin", or a hard abort inside a node NLP). Running each
branch-and-bound in a separate interpreter (`python -m coolingnet.optimization.isolation`)
turns such events into a recoverable `None`, after which the caller retries with a
conservative configuration or falls back to a known feasible design.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _run_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from coolingnet.config.schema import CaseStudy
    from coolingnet.network.graph import build_network
    from coolingnet.optimization.model import build_model, initialize_from_simulation
    from coolingnet.optimization.problems import load_warm_start
    from coolingnet.optimization.results import Solution
    from coolingnet.optimization.solvers import SolverSettings, solve_model
    from coolingnet.optimization.spec import Design, ProblemSpec
    from coolingnet.simulation.fixed_design import simulate_design

    case = CaseStudy.model_validate(payload["case"])
    spec = ProblemSpec.from_dict(payload["spec"], case)
    settings = SolverSettings(**payload["settings"])
    net = build_network(case.network)
    m = build_model(case, spec, net)
    sim = simulate_design(
        case,
        Design.from_case(case),
        hot_flow_factor=spec.hot_flow_factor,
        tower_model=spec.tower_model,
        network=net,
        penalty_factor=spec.penalty_factor,
    )
    initialize_from_simulation(m, sim)
    if payload.get("warm_start") is not None:
        load_warm_start(m, Solution.from_dict(payload["warm_start"]))
    report = solve_model(m, settings)
    return Solution.from_model(m, report, spec.label).to_dict()


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - child process entry point
    argv = sys.argv[1:] if argv is None else argv
    out_path = Path(argv[0])
    payload = json.load(sys.stdin)
    try:
        result = {"ok": True, "solution": _run_payload(payload)}
    except Exception:
        result = {"ok": False, "error": traceback.format_exc()}
    out_path.write_text(json.dumps(result, default=float))
    return 0


def solve_in_subprocess(case, spec, settings, warm_start=None, *, grace_s: float = 180.0):
    """Return a `Solution` (possibly with termination 'error') or None if the child crashed."""
    from coolingnet.optimization.results import Solution

    payload = {
        "case": case.model_dump(mode="json"),
        "spec": spec.to_dict(),
        "settings": {**asdict(settings), "isolate": False},
        "warm_start": warm_start.to_dict() if warm_start is not None else None,
    }
    with tempfile.TemporaryDirectory(prefix="coolingnet_child_") as td:
        out_path = Path(td) / "result.json"
        cmd = [sys.executable, "-m", "coolingnet.optimization.isolation", str(out_path)]
        try:
            proc = subprocess.run(
                cmd,
                input=json.dumps(payload, default=float),
                text=True,
                timeout=float(settings.time_limit_s) + grace_s,
                stdout=None if settings.verbose else subprocess.DEVNULL,
                stderr=None if settings.verbose else subprocess.DEVNULL,
                check=False,
            )
        except subprocess.TimeoutExpired:
            log.warning("%s: solver child exceeded the time limit and was killed", spec.label)
            return None
        if not out_path.exists():
            log.warning(
                "%s: solver child process ended abnormally (exit code %s)",
                spec.label,
                proc.returncode,
            )
            return None
        result = json.loads(out_path.read_text())
    if not result.get("ok"):
        log.warning("%s: solver child raised:\n%s", spec.label, result.get("error"))
        return None
    return Solution.from_dict(result["solution"])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
