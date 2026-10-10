"""Configuration schema and YAML loader (Section 3.1 data of the paper)."""

from __future__ import annotations

import copy

import pytest
import yaml
from pydantic import ValidationError

from coolingnet import dump_case, load_case
from coolingnet.config.loader import paper_case_path
from coolingnet.config.schema import CaseStudy


@pytest.fixture(scope="module")
def raw_case() -> dict:
    with paper_case_path().open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_paper_case_loads(case):
    assert isinstance(case, CaseStudy)
    assert case.name.startswith("Souza, Levy & Costa")
    assert len(case.network.edges) == 23
    assert len(case.heat_exchangers) == 5
    assert set(case.heat_exchangers) == {"E-101", "E-102", "E-103", "E-104", "E-105"}
    assert len(case.pipes.catalogue) == 20
    assert list(case.pumps.options) == ["1", "2", "3", "4"]


def test_heat_exchanger_resolves_defaults(case):
    he = case.heat_exchanger("E-101")
    assert he.tag == "E-101"
    assert he.edge_id == 19
    # values from Tables 5-6
    assert he.area_m2 == pytest.approx(27.3)
    assert he.hot_outlet_spec_C == pytest.approx(65.0)
    # values inherited from heat_exchanger_defaults
    assert he.penalty_factor_USD_per_C_y == pytest.approx(12500.0)
    assert he.tube_outer_diameter_m == pytest.approx(0.0207)
    assert he.tube_inner_diameter_m == pytest.approx(0.01905)
    assert he.hot_film_exponent == pytest.approx(0.6)
    assert he.water_film_exponent == pytest.approx(0.8)
    assert he.head_loss_exponent == pytest.approx(1.852)
    assert he.hot_heat_capacity_flow_design_W_K == pytest.approx(12.0 * 2200.0)


def test_resolved_heat_exchangers_follow_network_order(case):
    tags = [h.tag for h in case.resolved_heat_exchangers]
    assert tags == ["E-101", "E-102", "E-103", "E-104", "E-105"]


def test_per_exchanger_override_wins_over_default(case):
    spec = case.heat_exchangers["E-101"].model_copy(update={"penalty_factor_USD_per_C_y": 99.0})
    modified = case.with_updates(heat_exchangers={**case.heat_exchangers, "E-101": spec})
    assert modified.heat_exchanger("E-101").penalty_factor_USD_per_C_y == pytest.approx(99.0)
    assert modified.heat_exchanger("E-102").penalty_factor_USD_per_C_y == pytest.approx(12500.0)


def test_edge_with_missing_heat_exchanger_tag_raises(raw_case):
    bad = copy.deepcopy(raw_case)
    he_edges = [e for e in bad["network"]["edges"] if e["kind"] == "heat_exchanger"]
    he_edges[-1]["tag"] = "E-999"
    with pytest.raises(ValidationError, match="heat exchanger tags"):
        CaseStudy.model_validate(bad)


def test_pipe_with_diameter_outside_catalogue_raises(raw_case):
    bad = copy.deepcopy(raw_case)
    pipe = next(e for e in bad["network"]["edges"] if e["kind"] == "pipe")
    pipe["diameter_in"] = 7.3
    # NOTE: the cross-check validator lets the `KeyError` of `PipeCatalogue.by_nominal`
    # escape, so pydantic does not wrap it into a ValidationError.
    with pytest.raises((ValidationError, KeyError), match="not in the catalogue"):
        CaseStudy.model_validate(bad)


def test_pump_with_unknown_option_raises(raw_case):
    bad = copy.deepcopy(raw_case)
    pump = next(e for e in bad["network"]["edges"] if e["kind"] == "pump")
    pump["option"] = "9"
    with pytest.raises(ValidationError, match="not in the catalogue"):
        CaseStudy.model_validate(bad)


def test_unknown_field_is_rejected(raw_case):
    bad = copy.deepcopy(raw_case)
    bad["water"]["viscosity"] = 1.0
    with pytest.raises(ValidationError):
        CaseStudy.model_validate(bad)


def test_dump_then_load_round_trip(case, tmp_path):
    path = dump_case(case, tmp_path / "sub" / "case.yaml")
    assert path.exists()
    reloaded = load_case(path)
    original = case.model_dump()
    again = reloaded.model_dump()
    assert again == original
    assert reloaded.heat_exchanger("E-103") == case.heat_exchanger("E-103")


def test_dump_then_load_round_trip_preserves_layout_keys(case, tmp_path):
    """Integer node ids of `network.layout` survive the YAML round trip (coerced on load)."""
    reloaded = load_case(dump_case(case, tmp_path / "case.yaml"))
    assert reloaded.model_dump() == case.model_dump()
