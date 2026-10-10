"""Problem specification: which scenario / variant of the MINLP to build."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from coolingnet.config.schema import CaseStudy, EdgeId

Objective = Literal["total_cost", "cost_without_penalty", "flow_deviation"]
TowerModel = Literal["merkel", "fixed_inlet"]
PipeHeadFormulation = Literal["binary_product", "zq_power"]
PenaltyFormulation = Literal["auto", "epigraph", "binary", "post"]


@dataclass(frozen=True)
class Design:
    """A network design: nominal diameter of every pipe and option of every pump."""

    pipe_diameters_in: dict[EdgeId, float]
    pump_options: dict[EdgeId, str]

    @classmethod
    def from_case(cls, case: CaseStudy) -> Design:
        """The *existing* design described in the network configuration."""
        return cls(
            pipe_diameters_in={p.id: p.diameter_in for p in case.network.pipes},
            pump_options={u.id: u.option for u in case.network.pumps},
        )

    def changed_pipes(self, other: Design) -> list[EdgeId]:
        return [k for k, v in self.pipe_diameters_in.items() if abs(other.pipe_diameters_in[k] - v) > 1e-9]

    def changed_pumps(self, other: Design) -> list[EdgeId]:
        return [k for k, v in self.pump_options.items() if other.pump_options[k] != v]

    def to_dict(self) -> dict:
        return {
            "pipe_diameters_in": {str(k): v for k, v in self.pipe_diameters_in.items()},
            "pump_options": {str(k): v for k, v in self.pump_options.items()},
        }

    @classmethod
    def from_dict(cls, d: dict, case: CaseStudy) -> Design:
        """Inverse of `to_dict` (edge ids are matched by their string form)."""
        pipes = {p.id: float(d["pipe_diameters_in"][str(p.id)]) for p in case.network.pipes}
        pumps = {u.id: str(d["pump_options"][str(u.id)]) for u in case.network.pumps}
        return cls(pipe_diameters_in=pipes, pump_options=pumps)


@dataclass(frozen=True)
class ProblemSpec:
    """All switches of the optimization model (Section 2.4 and the result sections).

    Attributes
    ----------
    hot_flow_factor:
        Multiplier of the design hot stream flow rates (1.0 = design, 1.2 = current
        scenario of Section 3.2). Film coefficients follow a power law (exponent
        `hot_film_exponent`).
    penalty_factor:
        Override of the penalty factor pen_k [USD/(y degC)], scalar or per tag.
        `None` keeps the values of the case study.
    budget:
        Budget limit B [USD/y] of Eq. (46). `None` = unconstrained, `0.0` = no
        available budget (only valve manipulation is possible).
    design_free:
        If False the pipes and pump are fixed to `existing_design` (pure simulation
        of the network, or valve-only optimization when `valves_free`).
    valves_free:
        If False every valve head loss is fixed to zero (fully open valves).
    objective:
        "total_cost" = Eq. (55); "cost_without_penalty" = Cpipe + Cpump + Coper;
        "flow_deviation" = sum of squared deviations from `target_flows_kg_s`
        (purely hydraulic approach of Lee et al., Section 3.7).
    tower_model:
        "merkel" = Eqs. (32)-(37); "fixed_inlet" = water supply temperature fixed
        at the design inlet temperature (used to compute the desired flow rates).
    hydraulics:
        False builds only the thermal equations with free water flow rates
        (used with `fix_hot_outlet_to_spec` to compute the desired flow rates).
    penalty_formulation:
        "binary" = Eqs. (51)-(54) of the paper (big-M with the binary y_he);
        "epigraph" = che >= pen (T_out - T_spe), che >= 0, which is exact whenever
        Cpen is minimized (no binaries, better conditioned); "post" = penalties are
        not modelled, only evaluated from the outlet temperatures after the solve
        (objectives that do not contain Cpen); "auto" picks "epigraph" when Cpen is
        part of the objective and "post" otherwise.
    """

    @property
    def penalty_mode(self) -> str:
        """'epigraph' (Cpen minimized), 'binary' (Eqs. 51-54) or 'post' (penalties evaluated after the solve)."""
        if self.penalty_formulation != "auto":
            return self.penalty_formulation
        return "epigraph" if self.objective == "total_cost" else "post"

    @property
    def uses_binary_penalty(self) -> bool:
        return self.penalty_mode == "binary"

    hot_flow_factor: float = 1.0
    penalty_factor: float | dict[str, float] | None = None
    budget: float | None = None
    design_free: bool = True
    valves_free: bool = True
    objective: Objective = "total_cost"
    target_flows_kg_s: dict[str, float] | None = None
    flow_deviation_scale: float = 1000.0
    tower_model: TowerModel = "merkel"
    hydraulics: bool = True
    fix_hot_outlet_to_spec: bool = False
    existing_design: Design | None = None
    pipe_head_formulation: PipeHeadFormulation = "binary_product"
    penalty_formulation: PenaltyFormulation = "auto"
    allow_downsizing: bool = True
    label: str = ""
    extra: dict = field(default_factory=dict)

    def penalty_of(self, case: CaseStudy, tag: str) -> float:
        if self.penalty_factor is None:
            return case.heat_exchanger(tag).penalty_factor_USD_per_C_y
        if isinstance(self.penalty_factor, dict):
            return float(self.penalty_factor[tag])
        return float(self.penalty_factor)

    def with_(self, **changes) -> ProblemSpec:
        from dataclasses import replace

        return replace(self, **changes)

    @classmethod
    def from_dict(cls, d: dict, case: CaseStudy) -> ProblemSpec:
        data = dict(d)
        if data.get("existing_design") is not None:
            data["existing_design"] = Design.from_dict(data["existing_design"], case)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return {
            "hot_flow_factor": self.hot_flow_factor,
            "penalty_factor": self.penalty_factor,
            "budget": self.budget,
            "design_free": self.design_free,
            "valves_free": self.valves_free,
            "objective": self.objective,
            "target_flows_kg_s": self.target_flows_kg_s,
            "flow_deviation_scale": self.flow_deviation_scale,
            "tower_model": self.tower_model,
            "hydraulics": self.hydraulics,
            "fix_hot_outlet_to_spec": self.fix_hot_outlet_to_spec,
            "existing_design": self.existing_design.to_dict() if self.existing_design else None,
            "pipe_head_formulation": self.pipe_head_formulation,
            "penalty_formulation": self.penalty_formulation,
            "allow_downsizing": self.allow_downsizing,
            "label": self.label,
            "extra": self.extra,
        }
