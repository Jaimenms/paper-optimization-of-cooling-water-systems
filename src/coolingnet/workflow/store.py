"""Flat JSON store of solutions (one file per run, plus an index), used by the notebooks."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from coolingnet.optimization.results import Solution


class ResultStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ single runs
    def path(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def has(self, name: str) -> bool:
        return self.path(name).exists()

    def save(self, name: str, solution: Solution) -> Path:
        solution.meta = {**solution.meta, "saved_at": datetime.now(UTC).isoformat(), "name": name}
        p = solution.to_json(self.path(name))
        self._update_index(name, solution)
        return p

    def load(self, name: str) -> Solution:
        if not self.has(name):
            raise FileNotFoundError(f"no cached result named {name!r} in {self.root}")
        return Solution.from_json(self.path(name))

    # ------------------------------------------------------------- sweeps
    def sweep_dir(self, name: str) -> Path:
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_sweep(self, name: str, solutions: list[Solution]) -> Path:
        d = self.sweep_dir(name)
        for old in d.glob("*.json"):
            old.unlink()
        for i, s in enumerate(solutions):
            s.meta = {**s.meta, "sweep": name, "position": i}
            s.to_json(d / f"{i:04d}.json")
        self._update_index(name, None, count=len(solutions))
        return d

    def append_to_sweep(self, name: str, solution: Solution, position: int) -> Path:
        d = self.sweep_dir(name)
        solution.meta = {**solution.meta, "sweep": name, "position": position}
        return solution.to_json(d / f"{position:04d}.json")

    def load_sweep(self, name: str) -> list[Solution]:
        d = self.root / name
        if not d.exists():
            raise FileNotFoundError(f"no cached sweep named {name!r} in {self.root}")
        return [Solution.from_json(p) for p in sorted(d.glob("*.json"))]

    def has_sweep(self, name: str, expected: int | None = None) -> bool:
        d = self.root / name
        if not d.exists():
            return False
        n = len(list(d.glob("*.json")))
        return n > 0 if expected is None else n == expected

    # -------------------------------------------------------------- index
    def _update_index(self, name: str, solution: Solution | None, count: int | None = None) -> None:
        idx_path = self.root / "index.json"
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else {}
        entry = {"updated_at": datetime.now(UTC).isoformat()}
        if solution is not None:
            entry.update(
                {
                    "label": solution.label,
                    "termination": solution.report.get("termination"),
                    "objective": solution.costs.get("fob"),
                    "gap": solution.report.get("gap"),
                    "time_s": solution.report.get("time_s"),
                }
            )
        if count is not None:
            entry["count"] = count
        idx[name] = entry
        idx_path.write_text(json.dumps(idx, indent=1))

    def index(self) -> dict:
        idx_path = self.root / "index.json"
        return json.loads(idx_path.read_text()) if idx_path.exists() else {}
