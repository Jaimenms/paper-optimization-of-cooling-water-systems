"""Pydantic schema of a cooling water debottlenecking case study.

The schema mirrors the data of Souza, Levy & Costa (2018), Section 3.1, but is
generic: any digraph of pipes, one (or more) pumps and heat exchangers aligned
in parallel between a supply node (tower basin) and a return node (tower top)
can be described.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NodeId = int | str
EdgeId = int | str


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- #
# Network topology
# --------------------------------------------------------------------------- #
class PipeEdge(_Strict):
    """Pipe section (set PI). `diameter_in` is the *existing* nominal diameter."""

    id: EdgeId
    kind: Literal["pipe"] = "pipe"
    tail: NodeId
    head: NodeId
    length_m: float = Field(gt=0)
    diameter_in: float = Field(gt=0)

    @property
    def label(self) -> str:
        return str(self.id)


class PumpEdge(_Strict):
    """Pump (set PU). `option` names the *existing* pump alternative."""

    id: EdgeId
    kind: Literal["pump"] = "pump"
    tail: NodeId
    head: NodeId
    option: str

    @property
    def label(self) -> str:
        return str(self.id)


class HeatExchangerEdge(_Strict):
    """Heat exchanger / cooler (set HE). Data are looked up by `tag`."""

    id: EdgeId
    kind: Literal["heat_exchanger"] = "heat_exchanger"
    tail: NodeId
    head: NodeId
    tag: str

    @property
    def label(self) -> str:
        return self.tag


Edge = Annotated[PipeEdge | PumpEdge | HeatExchangerEdge, Field(discriminator="kind")]


class NetworkConfig(_Strict):
    supply_node: NodeId
    return_node: NodeId
    elevation_difference_m: float = Field(ge=0, description="Δz: tower top minus basin")
    edges: list[Edge]
    layout: dict[NodeId, tuple[float, float]] | None = Field(
        default=None, description="Optional (x, y) drawing coordinates of the nodes"
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_layout_keys(cls, data):
        """YAML/JSON turn integer node ids of `layout` into strings; map them back to the node ids."""
        if not isinstance(data, dict) or not data.get("layout") or not data.get("edges"):
            return data
        node_ids: set = set()
        for e in data["edges"]:
            if isinstance(e, dict):
                node_ids.update((e.get("tail"), e.get("head")))
            else:
                node_ids.update((getattr(e, "tail", None), getattr(e, "head", None)))
        by_str = {str(n): n for n in node_ids}
        layout = {}
        for k, v in dict(data["layout"]).items():
            key = k if k in node_ids else by_str.get(str(k), k)
            layout[key] = tuple(v) if isinstance(v, (list, tuple)) else v
        return {**data, "layout": layout}

    @model_validator(mode="after")
    def _check_unique(self) -> NetworkConfig:
        ids = [e.id for e in self.edges]
        if len(set(ids)) != len(ids):
            raise ValueError("edge ids must be unique")
        tags = [e.tag for e in self.edges if isinstance(e, HeatExchangerEdge)]
        if len(set(tags)) != len(tags):
            raise ValueError("heat exchanger tags must be unique")
        if not any(isinstance(e, HeatExchangerEdge) for e in self.edges):
            raise ValueError("the network needs at least one heat exchanger")
        if not any(isinstance(e, PumpEdge) for e in self.edges):
            raise ValueError("the network needs at least one pump")
        for e in self.edges:
            if e.tail == e.head:
                raise ValueError(f"edge {e.id} is a self loop")
        return self

    @property
    def pipes(self) -> list[PipeEdge]:
        return [e for e in self.edges if isinstance(e, PipeEdge)]

    @property
    def pumps(self) -> list[PumpEdge]:
        return [e for e in self.edges if isinstance(e, PumpEdge)]

    @property
    def heat_exchangers(self) -> list[HeatExchangerEdge]:
        return [e for e in self.edges if isinstance(e, HeatExchangerEdge)]


# --------------------------------------------------------------------------- #
# Heat exchangers
# --------------------------------------------------------------------------- #
class HeatExchangerDefaults(_Strict):
    tube_outer_diameter_m: float = Field(gt=0)
    tube_inner_diameter_m: float = Field(gt=0)
    wall_conductivity_W_mK: float = Field(gt=0)
    penalty_factor_USD_per_C_y: float = Field(ge=0)
    hot_outlet_min_C: float
    hot_outlet_max_C: float
    head_loss_exponent: float = 1.852
    water_film_exponent: float = 0.8
    hot_film_exponent: float = 0.6


class HeatExchangerSpec(_Strict):
    """Design data of one cooler (Tables 5 and 6). `None` fields fall back to defaults."""

    area_m2: float = Field(gt=0)
    hot_flow_design_kg_s: float = Field(gt=0)
    water_flow_design_kg_s: float = Field(gt=0)
    hot_inlet_C: float
    hot_outlet_spec_C: float
    water_inlet_design_C: float
    water_outlet_design_C: float
    cp_hot_J_kgK: float = Field(gt=0)
    h_water_design_W_m2K: float = Field(gt=0)
    h_hot_design_W_m2K: float = Field(gt=0)
    fouling_m2K_W: float = Field(ge=0)
    head_loss_design_m: float = Field(gt=0)
    # optional overrides of the defaults
    tube_outer_diameter_m: float | None = None
    tube_inner_diameter_m: float | None = None
    wall_conductivity_W_mK: float | None = None
    penalty_factor_USD_per_C_y: float | None = None
    hot_outlet_min_C: float | None = None
    hot_outlet_max_C: float | None = None
    head_loss_exponent: float | None = None
    water_film_exponent: float | None = None
    hot_film_exponent: float | None = None


class ResolvedHeatExchanger(_Strict):
    """A heat exchanger with every parameter resolved (spec merged with defaults)."""

    tag: str
    edge_id: EdgeId
    area_m2: float
    hot_flow_design_kg_s: float
    water_flow_design_kg_s: float
    hot_inlet_C: float
    hot_outlet_spec_C: float
    water_inlet_design_C: float
    water_outlet_design_C: float
    cp_hot_J_kgK: float
    h_water_design_W_m2K: float
    h_hot_design_W_m2K: float
    fouling_m2K_W: float
    head_loss_design_m: float
    tube_outer_diameter_m: float
    tube_inner_diameter_m: float
    wall_conductivity_W_mK: float
    penalty_factor_USD_per_C_y: float
    hot_outlet_min_C: float
    hot_outlet_max_C: float
    head_loss_exponent: float
    water_film_exponent: float
    hot_film_exponent: float

    @property
    def hot_heat_capacity_flow_design_W_K(self) -> float:
        return self.hot_flow_design_kg_s * self.cp_hot_J_kgK


# --------------------------------------------------------------------------- #
# Catalogues
# --------------------------------------------------------------------------- #
class PipeDiameter(_Strict):
    nominal_in: float = Field(gt=0)
    inner_m: float = Field(gt=0)

    @property
    def key(self) -> str:
        """Stable label used as index in the optimization model (e.g. '10.0')."""
        return f"{self.nominal_in:g}"


class PipeCatalogue(_Strict):
    hazen_williams_c: float = Field(gt=0)
    cost_c1: float
    cost_m: float
    v_max_m_s: float = Field(gt=0)
    v_min_m_s: float = Field(ge=0)
    q_min_m3_s: float = Field(ge=0)
    q_max_m3_s: float = Field(gt=0)
    catalogue: list[PipeDiameter]

    @model_validator(mode="after")
    def _check(self) -> PipeCatalogue:
        noms = [d.nominal_in for d in self.catalogue]
        if len(set(noms)) != len(noms):
            raise ValueError("duplicated nominal diameters in the catalogue")
        if noms != sorted(noms):
            raise ValueError("catalogue diameters must be sorted in ascending order")
        if self.v_min_m_s >= self.v_max_m_s:
            raise ValueError("v_min must be lower than v_max")
        return self

    def by_nominal(self, nominal_in: float) -> PipeDiameter:
        for d in self.catalogue:
            if abs(d.nominal_in - nominal_in) < 1e-9:
                return d
        raise KeyError(f"nominal diameter {nominal_in} in is not in the catalogue")

    @property
    def keys(self) -> list[str]:
        return [d.key for d in self.catalogue]


class PumpOption(_Strict):
    """Pump curve head(q) = sum_i a_i q^i, with q in m3/s and head in m."""

    coefficients: list[float] = Field(min_length=1)


class PumpCatalogue(_Strict):
    efficiency: float = Field(gt=0, le=1)
    design_flow_m3_s: float = Field(gt=0)
    cost_FI: float
    cost_Fms: float
    cost_Fm: float
    cost_b: list[float] = Field(min_length=1)
    options: dict[str, PumpOption]

    @property
    def keys(self) -> list[str]:
        return list(self.options.keys())


# --------------------------------------------------------------------------- #
# Tower, water, economics, scenarios
# --------------------------------------------------------------------------- #
class SaturationEnthalpyFit(_Strict):
    a: float
    b: float
    c: float
    d: float


class CoolingTowerSpec(_Strict):
    wet_bulb_C: float
    max_feed_temperature_C: float
    air_flow_kg_s: float = Field(gt=0)
    packing_height_m: float = Field(gt=0)
    C_un: float = Field(gt=0)
    n: float
    atmospheric_air_enthalpy_J_kg: float
    saturation_enthalpy: SaturationEnthalpyFit
    quadrature_points: list[float] = Field(min_length=1)
    merkel_regularization_J_kg: float = Field(
        default=1.0, description="small term added to Hsat-H to avoid division by zero"
    )
    min_enthalpy_driving_force_J_kg: float = Field(
        default=100.0,
        description="Hsat - H >= this value at every quadrature point (air must stay unsaturated: "
        "excludes the spurious roots of the regularized Merkel integral)",
    )


class WaterProperties(_Strict):
    density_kg_m3: float = Field(gt=0)
    cp_J_kgK: float = Field(gt=0)


class EconomicParams(_Strict):
    operating_hours_per_year: float = Field(gt=0)
    energy_cost_USD_kWh: float = Field(ge=0)
    interest_rate: float = Field(gt=0)
    project_years: int = Field(gt=0)
    gravity_m_s2: float = 9.81


class BudgetSweep(_Strict):
    max_USD_y: float = Field(gt=0)
    steps: int = Field(gt=0)


class PenaltySweep(_Strict):
    max_factor: float = Field(gt=0)
    steps: int = Field(gt=0)


class ScenarioSpec(_Strict):
    hot_flow_increase_factor: float = Field(gt=0)
    penalty_cases: dict[str, float]
    budget_cases: dict[str, float]
    budget_sweep: BudgetSweep
    penalty_sweep: PenaltySweep


# --------------------------------------------------------------------------- #
# Case study
# --------------------------------------------------------------------------- #
class CaseStudy(_Strict):
    name: str
    network: NetworkConfig
    heat_exchangers: dict[str, HeatExchangerSpec]
    heat_exchanger_defaults: HeatExchangerDefaults
    pipes: PipeCatalogue
    pumps: PumpCatalogue
    cooling_tower: CoolingTowerSpec
    water: WaterProperties
    economics: EconomicParams
    scenarios: ScenarioSpec

    @model_validator(mode="after")
    def _cross_check(self) -> CaseStudy:
        tags_in_network = {e.tag for e in self.network.heat_exchangers}
        tags_in_data = set(self.heat_exchangers)
        if tags_in_network != tags_in_data:
            raise ValueError(
                "heat exchanger tags of the network and of the data block differ: "
                f"network={sorted(tags_in_network)} data={sorted(tags_in_data)}"
            )
        for p in self.network.pipes:
            try:
                self.pipes.by_nominal(p.diameter_in)
            except KeyError as exc:
                raise ValueError(f"pipe edge {p.id}: {exc.args[0]}") from exc
        for pu in self.network.pumps:
            if pu.option not in self.pumps.options:
                raise ValueError(f"pump edge {pu.id}: option {pu.option!r} is not in the catalogue")
        return self

    # -- convenience accessors -------------------------------------------------
    def heat_exchanger(self, tag: str) -> ResolvedHeatExchanger:
        spec = self.heat_exchangers[tag]
        edge = next(e for e in self.network.heat_exchangers if e.tag == tag)
        defaults = self.heat_exchanger_defaults.model_dump()
        merged = {k: v for k, v in spec.model_dump().items() if v is not None}
        resolved = {**defaults, **merged}
        return ResolvedHeatExchanger(tag=tag, edge_id=edge.id, **resolved)

    @property
    def resolved_heat_exchangers(self) -> list[ResolvedHeatExchanger]:
        return [self.heat_exchanger(e.tag) for e in self.network.heat_exchangers]

    def with_updates(self, **updates) -> CaseStudy:
        """Return a copy with top-level sections replaced (pydantic `model_copy`)."""
        return self.model_copy(update=updates, deep=True)
