"""Solution container, JSON result store and the pandas tables of the paper."""

from __future__ import annotations

import json

import pytest

from coolingnet.optimization import ProblemSpec, Solution, SolveReport, build_model
from coolingnet.optimization.model import initialize_from_simulation
from coolingnet.reporting.tables import (
    table_circuits,
    table_costs,
    table_heat_exchangers_performance,
    table_no_budget,
    table_pipes,
    table_pumps,
)
from coolingnet.simulation import simulate_design
from coolingnet.workflow import ResultStore


def _report(**overrides) -> SolveReport:
    base = dict(
        solver="none",
        status="initialized",
        termination="feasible",
        objective=None,
        bound=None,
        gap=None,
        time_s=0.0,
    )
    return SolveReport(**{**base, **overrides})


@pytest.fixture(scope="module")
def solution(case, network) -> Solution:
    """A Solution snapshot of the existing design, built from the simulator without solving."""
    m = build_model(
        case, ProblemSpec(design_free=False, valves_free=False, label="snapshot"), network
    )
    initialize_from_simulation(m, simulate_design(case, network=network))
    return Solution.from_model(m, _report(objective=20160.0))


@pytest.fixture(scope="module")
def solution_current(case, network) -> Solution:
    spec = ProblemSpec(
        hot_flow_factor=1.2, design_free=False, valves_free=False, label="snapshot_x1.2"
    )
    m = build_model(case, spec, network)
    initialize_from_simulation(m, simulate_design(case, hot_flow_factor=1.2, network=network))
    return Solution.from_model(m, _report())


# --------------------------------------------------------------------------- Solution
def test_solution_content(solution, tags):
    assert solution.label == "snapshot"
    assert solution.ok
    assert solution.objective == pytest.approx(20160.19, abs=0.01)
    assert solution.costs["cpipe"] == 0.0 and solution.costs["cpump"] == 0.0
    assert solution.costs["cpen"] == 0.0
    assert solution.costs["total_cost"] == pytest.approx(solution.costs["fob"])
    assert solution.budget is None
    assert solution.penalty_factor is None
    df = solution.exchangers_df()
    assert list(df.index) == tags
    for col in ("k_kg_s", "T_hot_out_C", "valve_head_loss_m", "penalty_USD_y"):
        assert col in df.columns
    assert df["k_kg_s"].tolist() == pytest.approx([11.92, 28.85, 35.57, 15.53, 3.23], abs=0.01)
    assert df["T_hot_out_C"].tolist() == pytest.approx(
        [63.48, 78.39, 39.66, 40.91, 39.75], abs=0.01
    )
    assert solution.pipe_diameters()["1"] == 10.0
    assert set(solution.pipe_diameters()) == {str(i) for i in range(1, 19) if i != 2}
    assert solution.pump_options() == {"2": "1"}
    assert len(solution.edges_df()) == 23
    assert len(solution.pipes_df()) == 17
    assert len(solution.circuits_df()) == 5
    assert solution.tower["T_w_in_C"] == pytest.approx(32.20, abs=0.01)
    assert solution.meta["case"].startswith("Souza")


def test_solution_json_round_trip(solution, tmp_path):
    path = solution.to_json(tmp_path / "nested" / "sol.json")
    assert path.exists()
    again = Solution.from_json(path)
    assert again.to_dict() == solution.to_dict()
    assert Solution.from_dict(solution.to_dict()).to_dict() == solution.to_dict()
    # plain JSON (no numpy scalars left behind)
    json.loads(path.read_text())


# -------------------------------------------------------------------------- ResultStore
def test_result_store_save_load_has_index(solution, tmp_path):
    store = ResultStore(tmp_path / "results")
    assert (tmp_path / "results").is_dir()
    assert not store.has("initial")
    assert store.index() == {}
    with pytest.raises(FileNotFoundError):
        store.load("initial")

    path = store.save("initial", solution)
    assert path == store.path("initial") and path.exists()
    assert store.has("initial")
    assert solution.meta["name"] == "initial" and "saved_at" in solution.meta

    loaded = store.load("initial")
    assert loaded.to_dict() == solution.to_dict()

    idx = store.index()
    assert set(idx) == {"initial"}
    entry = idx["initial"]
    assert entry["label"] == "snapshot"
    assert entry["termination"] == "feasible"
    assert entry["objective"] == pytest.approx(solution.costs["fob"])
    assert entry["gap"] is None and entry["time_s"] == 0.0
    assert "updated_at" in entry


def test_result_store_sweeps(solution, solution_current, tmp_path):
    store = ResultStore(tmp_path / "results")
    assert not store.has_sweep("sweep")
    with pytest.raises(FileNotFoundError):
        store.load_sweep("sweep")

    d = store.save_sweep("sweep", [solution, solution_current])
    assert d == tmp_path / "results" / "sweep"
    assert sorted(p.name for p in d.glob("*.json")) == ["0000.json", "0001.json"]
    assert (
        store.has_sweep("sweep")
        and store.has_sweep("sweep", expected=2)
        and not store.has_sweep("sweep", expected=3)
    )
    assert store.index()["sweep"]["count"] == 2

    loaded = store.load_sweep("sweep")
    assert [s.label for s in loaded] == ["snapshot", "snapshot_x1.2"]
    assert [s.meta["position"] for s in loaded] == [0, 1]
    assert all(s.meta["sweep"] == "sweep" for s in loaded)
    assert loaded[1].to_dict() == solution_current.to_dict()

    # saving again replaces the old files
    store.save_sweep("sweep", [solution_current])
    assert store.has_sweep("sweep", expected=1)
    store.append_to_sweep("sweep", solution, position=7)
    assert sorted(p.name for p in d.glob("*.json")) == ["0000.json", "0007.json"]
    assert [s.label for s in store.load_sweep("sweep")] == ["snapshot_x1.2", "snapshot"]


# ------------------------------------------------------------------------------- tables
def test_table_pipes(case):
    df = table_pipes(case)
    assert df.shape == (17, 2)
    assert df.index.name == "Pipe section"
    assert df.loc[1, "Nominal diameter (in)"] == 10
    assert df.loc[1, "Length (m)"] == 10
    assert df.loc[13, "Nominal diameter (in)"] == 2
    assert df["Length (m)"].sum() == pytest.approx(1260.0)


def test_table_circuits(case, network):
    df = table_circuits(case)
    assert df.shape == (5, 1)
    assert df.loc[1, "Edges"] == "1, 2, 3, 9, E-101, 14, 8"
    assert table_circuits(case, network).equals(df)


def test_table_pumps(case):
    df = table_pumps(case)
    assert list(df.index) == ["1", "2", "3", "4"]
    assert df.loc["4"].tolist() == [-609.5, -198.0, 46.2]


def test_table_heat_exchangers_performance(case, solution, solution_current, tags):
    df = table_heat_exchangers_performance(case, solution, solution_current)
    assert df.shape[0] == 6
    assert list(df.index) == [*tags, "Total"]
    assert df.loc[tags, "Design condition (C)"].tolist() == [65.0, 80.0, 40.0, 41.0, 41.0]
    assert df.loc[tags, "Initial condition (C)"].tolist() == pytest.approx(
        [63.48, 78.39, 39.66, 40.91, 39.75], abs=0.01
    )
    assert df.loc[tags, "Current condition (C)"].tolist() == pytest.approx(
        [65.16, 81.59, 41.82, 42.81, 41.53], abs=0.01
    )
    assert df.loc["Total", "Current condition penalty (kUSD/y)"] == pytest.approx(73.71, abs=0.01)
    # the same solution twice also works (6 rows, zero penalty)
    same = table_heat_exchangers_performance(case, solution, solution)
    assert same.shape[0] == 6
    assert same.loc["Total", "Current condition penalty (kUSD/y)"] == 0.0


def test_table_no_budget(solution_current):
    df = table_no_budget(solution_current, solution_current)
    assert df.shape[0] == 6
    assert df.loc["Total", "Penalty (kUSD/y)"] == pytest.approx(73.71, abs=0.01)


def test_table_costs(solution, solution_current):
    costs = table_costs({"initial": solution, "current": solution_current})
    assert list(costs.index) == ["initial", "current"]
    assert costs.loc["current", "Penalty (kUSD/y)"] == pytest.approx(73.71, abs=0.01)
    assert costs.loc["initial", "Pipes changed"] == 0
    assert costs.loc["initial", "Pump option"] == "1"
