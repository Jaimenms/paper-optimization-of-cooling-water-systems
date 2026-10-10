"""Tables and figures of the paper, built from `Solution` objects."""

from coolingnet.reporting.export import export_all
from coolingnet.reporting.figures import (
    plot_budget_costs,
    plot_budget_interventions,
    plot_comparison_bars,
    plot_diameter_dotchart,
    plot_penalty_sweep,
    save_budget_animation,
)
from coolingnet.reporting.network_plot import plot_network
from coolingnet.reporting.tables import (
    table_budget_cases,
    table_circuits,
    table_costs,
    table_exchanger_design,
    table_heat_exchangers_performance,
    table_hydraulic_only,
    table_no_budget,
    table_pipes,
    table_problem_parameters,
    table_pump_cost_parameters,
    table_pumps,
    table_thermal_tasks,
    table_unlimited_budget,
)

__all__ = [
    "export_all",
    "plot_budget_costs",
    "plot_budget_interventions",
    "plot_comparison_bars",
    "plot_diameter_dotchart",
    "plot_network",
    "plot_penalty_sweep",
    "save_budget_animation",
    "table_budget_cases",
    "table_circuits",
    "table_costs",
    "table_exchanger_design",
    "table_heat_exchangers_performance",
    "table_hydraulic_only",
    "table_no_budget",
    "table_pipes",
    "table_problem_parameters",
    "table_pump_cost_parameters",
    "table_pumps",
    "table_thermal_tasks",
    "table_unlimited_budget",
]
