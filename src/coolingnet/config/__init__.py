"""Configuration schema and loaders (every paper parameter is data, not code)."""

from coolingnet.config.loader import dump_case, load_case, paper_case, paper_case_path
from coolingnet.config.schema import (
    CaseStudy,
    CoolingTowerSpec,
    EconomicParams,
    HeatExchangerEdge,
    HeatExchangerSpec,
    NetworkConfig,
    PipeCatalogue,
    PipeDiameter,
    PipeEdge,
    PumpCatalogue,
    PumpEdge,
    PumpOption,
    ResolvedHeatExchanger,
    ScenarioSpec,
    WaterProperties,
)

__all__ = [
    "CaseStudy",
    "CoolingTowerSpec",
    "EconomicParams",
    "HeatExchangerEdge",
    "HeatExchangerSpec",
    "NetworkConfig",
    "PipeCatalogue",
    "PipeDiameter",
    "PipeEdge",
    "PumpCatalogue",
    "PumpEdge",
    "PumpOption",
    "ResolvedHeatExchanger",
    "ScenarioSpec",
    "WaterProperties",
    "dump_case",
    "load_case",
    "paper_case",
    "paper_case_path",
]
