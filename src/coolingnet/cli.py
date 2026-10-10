"""Command line interface: `coolingnet --help`."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from coolingnet.config import dump_case, load_case
from coolingnet.network import build_network

app = typer.Typer(help="Optimization of cooling water system hydraulic debottlenecking (Souza, Levy & Costa, 2018).", no_args_is_help=True)
console = Console()


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging")) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


@app.command()
def export_config(path: Path = typer.Argument(..., help="Destination YAML file")) -> None:
    """Write the paper's configuration to a YAML file you can edit (network, catalogues, parameters)."""
    p = dump_case(load_case(), path)
    console.print(f"configuration written to [bold]{p}[/bold]")


@app.command()
def show_network(config: Path | None = typer.Option(None, "--config", "-c", help="Case YAML (default: paper case)")) -> None:
    """Print nodes, edges and the hydraulic circuits (Table 1)."""
    case = load_case(config)
    net = build_network(case.network)
    console.print(f"[bold]{case.name}[/bold]")
    console.print(f"{len(net.nodes)} nodes, {len(net.edges)} edges ({len(net.pipes)} pipes, {len(net.pumps)} pumps, {len(net.heat_exchangers)} heat exchangers)")
    t = Table(title="Hydraulic circuits")
    t.add_column("Circuit")
    t.add_column("Edges")
    for row in net.circuit_table():
        t.add_row(str(row["Circuit"]), str(row["Edges"]))
    console.print(t)


@app.command()
def solvers() -> None:
    """List the optimization back-ends available in this environment."""
    from coolingnet.optimization.solvers import available_solvers

    t = Table(title="Solvers")
    t.add_column("name")
    t.add_column("available")
    for k, v in available_solvers().items():
        t.add_row(k, "[green]yes[/green]" if v else "[red]no[/red]")
    console.print(t)


@app.command()
def simulate(
    config: Path | None = typer.Option(None, "--config", "-c"),
    hot_flow_factor: float = typer.Option(1.0, help="Multiplier of the design hot stream flow rates"),
) -> None:
    """Simulate the existing network (NumPy/SciPy, no optimization)."""
    from coolingnet.simulation import simulate_design

    case = load_case(config)
    r = simulate_design(case, hot_flow_factor=hot_flow_factor)
    t = Table(title=f"Existing network, hot flow x{hot_flow_factor:g} (T_w,in={r.T_w_in_C:.2f} C, T_feed={r.T_w_feed_C:.2f} C)")
    for col in ("tag", "k_kg_s", "T_hot_out_C", "T_hot_out_spec_C", "penalty_USD_y"):
        t.add_column(col, justify="right")
    for tag, row in r.exchangers.items():
        t.add_row(tag, f"{row['k_kg_s']:.2f}", f"{row['T_hot_out_C']:.2f}", f"{row['T_hot_out_spec_C']:.2f}", f"{row['penalty_USD_y']:.0f}")
    console.print(t)
    console.print(f"operating cost {r.operating_cost_USD_y:.1f} USD/y, penalty {r.penalty_USD_y:.1f} USD/y, converged={r.converged}")


@app.command()
def run(
    config: Path | None = typer.Option(None, "--config", "-c", help="Case YAML (default: paper case)"),
    results: Path = typer.Option(Path("results"), "--results", "-r", help="Result cache directory"),
    solver: str = typer.Option("nlpbb", help="Solver back-end: nlpbb (default, NLP branch-and-bound) | bonmin | scip | ipopt | <pyomo solver name>"),
    stages: str = typer.Option(",".join(["simulations", "no_budget", "unlimited", "budget_cases", "budget_sweep", "penalty_sweep", "literature"]), help="Comma separated stage list"),
    time_limit: float = typer.Option(900.0, help="Time limit per solve [s]"),
    budget_steps: int | None = typer.Option(None, help="Override number of budget sweep steps"),
    penalty_steps: int | None = typer.Option(None, help="Override number of penalty sweep steps"),
    force: bool = typer.Option(False, help="Ignore cached results"),
) -> None:
    """Run the paper's scenarios (cached in the results directory, used by the notebooks)."""
    from coolingnet.optimization.solvers import SolverSettings
    from coolingnet.workflow import PaperPipeline, PipelineConfig

    case = load_case(config)
    cfg = PipelineConfig(
        results_dir=results,
        solver=SolverSettings(name=solver, time_limit_s=time_limit),
        force=force,
        stages=tuple(s.strip() for s in stages.split(",") if s.strip()),
        budget_steps=budget_steps,
        penalty_steps=penalty_steps,
        progress=lambda msg: console.print(msg),
    )
    PaperPipeline(case, cfg).run()
    console.print(f"[bold green]done[/bold green] - results in {results}")


@app.command()
def figures(
    results: Path = typer.Option(Path("results"), "--results", "-r"),
    out: Path = typer.Option(Path("figures"), "--out", "-o"),
    config: Path | None = typer.Option(None, "--config", "-c"),
    fmt: str = typer.Option("png", help="png | pdf | svg"),
) -> None:
    """Render every figure and table of the paper from cached results."""
    import matplotlib

    matplotlib.use("Agg")  # headless rendering (the notebooks keep the inline backend)
    from coolingnet.reporting import export_all

    case = load_case(config)
    written = export_all(case, results, out, fmt=fmt)
    for p in written:
        console.print(f"  {p}")
    console.print(f"[bold green]{len(written)} files written to {out}[/bold green]")


if __name__ == "__main__":  # pragma: no cover
    app()
