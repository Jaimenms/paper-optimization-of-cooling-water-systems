"""Solution container: plain-data snapshot of a solved model (JSON serializable, pandas friendly)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import pyomo.environ as pyo

from coolingnet.optimization.model import selected_design
from coolingnet.optimization.solvers import SolveReport
from coolingnet.optimization.spec import Design, ProblemSpec
from coolingnet.physics.hydraulics import velocity


@dataclass
class Solution:
    """Everything needed to build the tables and figures of the paper for one run."""

    label: str
    spec: dict[str, Any]
    report: dict[str, Any]
    design: dict[str, Any]
    edges: list[dict[str, Any]]
    exchangers: list[dict[str, Any]]
    pumps: list[dict[str, Any]]
    circuits: list[dict[str, Any]]
    tower: dict[str, Any]
    costs: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------- accessors
    @property
    def ok(self) -> bool:
        return self.report.get("termination") in ("optimal", "feasible")

    @property
    def objective(self) -> float:
        return float(self.costs["fob"])

    @property
    def budget(self) -> float | None:
        return self.spec.get("budget")

    @property
    def penalty_factor(self) -> float | None:
        pf = self.spec.get("penalty_factor")
        if isinstance(pf, dict):
            return float(next(iter(pf.values())))
        return pf

    def pipe_diameters(self) -> dict[str, float]:
        return {str(k): float(v) for k, v in self.design["pipe_diameters_in"].items()}

    def pump_options(self) -> dict[str, str]:
        return {str(k): str(v) for k, v in self.design["pump_options"].items()}

    def exchangers_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.exchangers).set_index("tag")

    def edges_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.edges).set_index("id")

    def pipes_df(self) -> pd.DataFrame:
        df = self.edges_df()
        return df[df["kind"] == "pipe"]

    def circuits_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.circuits).set_index("circuit")

    def costs_series(self) -> pd.Series:
        return pd.Series(self.costs)

    # --------------------------------------------------------- serialization
    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "spec": self.spec,
            "report": self.report,
            "design": self.design,
            "edges": self.edges,
            "exchangers": self.exchangers,
            "pumps": self.pumps,
            "circuits": self.circuits,
            "tower": self.tower,
            "costs": self.costs,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Solution:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})

    def to_json(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=1, default=_json_default), encoding="utf-8")
        return p

    @classmethod
    def from_json(cls, path: str | Path) -> Solution:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # ------------------------------------------------------------ builders
    @classmethod
    def from_model(cls, m: pyo.ConcreteModel, report: SolveReport, label: str = "") -> Solution:
        spec: ProblemSpec = m.spec
        net = m.network
        case = m.case
        rho = case.water.density_kg_m3
        design: Design = selected_design(m)
        existing: Design = m.existing_design
        v = pyo.value
        hyd = spec.hydraulics

        edges = []
        for e in net.edges:
            row: dict[str, Any] = {
                "id": e.id,
                "label": e.label,
                "kind": e.kind,
                "tail": e.tail,
                "head": e.head,
                "q_m3_s": v(m.q[e.id]),
                "k_kg_s": rho * v(m.q[e.id]),
            }
            if e.kind == "pipe":
                row["length_m"] = e.length_m
                row["diameter_in"] = design.pipe_diameters_in[e.id]
                row["diameter_existing_in"] = existing.pipe_diameters_in[e.id]
                row["changed"] = abs(row["diameter_in"] - row["diameter_existing_in"]) > 1e-9
                if hyd:
                    row["head_loss_m"] = v(m.f_pipe[e.id])
                    row["velocity_m_s"] = v(m.v[e.id])
            elif e.kind == "pump":
                row["option"] = design.pump_options[e.id]
                row["option_existing"] = existing.pump_options[e.id]
                row["changed"] = row["option"] != row["option_existing"]
                if hyd:
                    row["head_m"] = v(m.f_pump[e.id])
            else:
                row["tag"] = e.tag
                if hyd:
                    row["head_loss_m"] = v(m.f_he[e.id])
            edges.append(row)

        circuits = []
        for c in net.circuits:
            circuits.append(
                {
                    "circuit": c.index,
                    "he_tag": c.he_tag,
                    "edges": [net.label(x) for x in c.edge_ids],
                    "q_m3_s": v(m.q[c.he_edge]),
                    "valve_head_loss_m": v(m.lvalve[c.index]) if hyd else 0.0,
                }
            )

        post_penalty = spec.penalty_mode == "post"

        def penalty_of(h_id, t_out: float) -> float:
            d = m.he_data[h_id]
            if post_penalty:
                return d["pen"] * max(0.0, t_out - d["spec"].hot_outlet_spec_C)
            return v(m.che[h_id])

        exchangers = []
        for h in net.heat_exchangers:
            d = m.he_data[h.id]
            spec_he = d["spec"]
            c = net.circuit_of(h.id)
            k_w = rho * v(m.q[h.id])
            t_hot_out = v(m.T_hot_out[h.id])
            exchangers.append(
                {
                    "tag": h.tag,
                    "edge_id": h.id,
                    "circuit": c.index,
                    "k_kg_s": k_w,
                    "k_design_kg_s": spec_he.water_flow_design_kg_s,
                    "hot_flow_kg_s": spec.hot_flow_factor * spec_he.hot_flow_design_kg_s,
                    "T_hot_in_C": spec_he.hot_inlet_C,
                    "T_hot_out_C": t_hot_out,
                    "T_hot_out_spec_C": spec_he.hot_outlet_spec_C,
                    "T_w_in_C": v(m.T_w_in),
                    "T_w_out_C": v(m.T_w_out[h.id]),
                    "effectiveness": v(m.P[h.id]),
                    "NTU": v(m.NTU[h.id]),
                    "CR": v(m.cr[h.id]),
                    "U_W_m2K": v(m.U[h.id]),
                    "h_w_W_m2K": v(m.h_w[h.id]),
                    "h_hot_W_m2K": d["h_hot"],
                    "duty_W": d["C_hot"] * (spec_he.hot_inlet_C - t_hot_out),
                    "penalty_factor": d["pen"],
                    "penalty_active": (v(m.y_he[h.id]) > 0.5) if hasattr(m, "y_he") else (penalty_of(h.id, t_hot_out) > 1e-6),
                    "penalty_USD_y": penalty_of(h.id, t_hot_out),
                    "valve_head_loss_m": v(m.lvalve[c.index]) if hyd else 0.0,
                    "head_loss_m": v(m.f_he[h.id]) if hyd else None,
                }
            )

        pumps = []
        for u in net.pumps:
            pumps.append(
                {
                    "id": u.id,
                    "option": design.pump_options[u.id],
                    "option_existing": existing.pump_options[u.id],
                    "q_m3_s": v(m.q[u.id]),
                    "k_kg_s": rho * v(m.q[u.id]),
                    "head_m": v(m.f_pump[u.id]) if hyd else None,
                    "operating_cost_USD_y": v(m.f_pump[u.id]) * rho * v(m.q[u.id]) * m.params["ope_factor"] if hyd else 0.0,
                }
            )

        tower = {
            "T_w_in_C": v(m.T_w_in),
            "T_w_feed_C": v(m.T_w_feed),
            "water_flow_kg_s": rho * sum(v(m.q[h.id]) for h in net.heat_exchangers),
            "merkel_integral": v(m.IM) if spec.tower_model == "merkel" else None,
            "tower_characteristic": v(m.IP) if spec.tower_model == "merkel" else None,
        }
        cpen = sum(x["penalty_USD_y"] for x in exchangers)
        costs = {
            "cpipe": v(m.cpipe),
            "cpump": v(m.cpump),
            "cope": v(m.cope),
            "cpen": cpen,
            "capital": v(m.cpipe) + v(m.cpump),
            "fob": v(m.fob),
            "total_cost": v(m.cpipe) + v(m.cpump) + v(m.cope) + cpen,
            "budget": spec.budget,
        }
        if spec.objective == "flow_deviation" and spec.target_flows_kg_s:
            costs["flow_deviation_kg2_s2"] = sum(
                (rho * v(m.q[h.id]) - spec.target_flows_kg_s[h.tag]) ** 2 for h in net.heat_exchangers
            )
        return cls(
            label=label or spec.label,
            spec=spec.to_dict(),
            report=report.to_dict(),
            design=design.to_dict(),
            edges=edges,
            exchangers=exchangers,
            pumps=pumps,
            circuits=circuits,
            tower=tower,
            costs=costs,
            meta={"case": case.name},
        )


def _json_default(o):
    import numpy as np

    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"not JSON serializable: {type(o)}")


def velocity_of(row: dict[str, Any], inner_diameter_m: float) -> float:
    return float(velocity(row["q_m3_s"], inner_diameter_m))
