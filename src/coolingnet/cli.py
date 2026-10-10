"""Command line interface: `coolingnet --help`.

Verbs shared by the series (docs/conventions.md): `info`, `validate`, `run`, `eval`, `figures`.
Extras: `simulate`, `show-network`, `export-config`, `solvers`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from coolingnet import __version__
from coolingnet.config import dump_case, load_case
from coolingnet.network import build_network

app = typer.Typer(
    help="Optimization of cooling water system hydraulic debottlenecking "
    "(Souza, Levy & Costa, Applied Thermal Engineering 128, 2018).",
    no_args_is_help=True,
)
console = Console()

CaseArg = typer.Argument(
    None, help="Case YAML file (default: the paper case packaged with coolingnet)"
)
ConfigOpt = typer.Option(
    None, "--config", "-c", help="Case YAML file (same as the positional argument)"
)


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging")) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _load(case: Path | None, config: Path | None):
    if case is not None and config is not None and case != config:
        raise typer.BadParameter("give the case file either as argument or with --config, not both")
    return load_case(case or config)


def _network_summary(case, net) -> None:
    console.print(f"[bold]{case.name}[/bold]")
    console.print(
        f"{len(net.nodes)} nodes, {len(net.edges)} edges ({len(net.pipes)} pipes, {len(net.pumps)} pumps, "
        f"{len(net.heat_exchangers)} heat exchangers), supply node {net.supply_node}, return node {net.return_node}"
    )
    t = Table(title="Hydraulic circuits (Table 1)")
    t.add_column("Circuit")
    t.add_column("Edges")
    for row in net.circuit_table():
        t.add_row(str(row["Circuit"]), str(row["Edges"]))
    console.print(t)


# --------------------------------------------------------------------------- #
# info / validate
# --------------------------------------------------------------------------- #
@app.command()
def info() -> None:
    """Paper reference, available cases, package version, solvers and cached results."""
    import json

    from coolingnet.config.loader import paper_case_path
    from coolingnet.optimization.solvers import available_solvers
    from coolingnet.paths import cases_dir, repo_root
    from coolingnet.reporting import paper_reference as REF

    console.print(f"[bold]coolingnet {__version__}[/bold] - Python reimplementation of")
    console.print(f"  {REF.citation()}")
    console.print()
    t = Table(title="Cases")
    t.add_column("file")
    t.add_column("name")
    t.add_row(str(paper_case_path()), load_case().name + " [packaged default]")
    root: Path | None
    try:
        root = repo_root()
        for p in sorted(cases_dir().glob("*.yaml")):
            try:
                name = load_case(p).name
            except Exception as exc:  # noqa: BLE001 - report, do not abort
                name = f"[red]invalid: {exc}[/red]"
            t.add_row(str(p.relative_to(root)), name)
    except FileNotFoundError:
        root = None
    console.print(t)
    t = Table(title="Solvers")
    t.add_column("name")
    t.add_column("available")
    for k, v in available_solvers().items():
        t.add_row(k, "[green]yes[/green]" if v else "[red]no[/red]")
    console.print(t)
    results = (root or Path.cwd()) / "results"
    idx_path = results / "index.json"
    if idx_path.exists():
        idx = json.loads(idx_path.read_text())
        console.print(f"cached results in {results}: {', '.join(idx)}")
    else:
        console.print(f"no cached results in {results} (run `make run`)")


@app.command()
def validate(case: Path = typer.Argument(..., help="Case YAML file to check")) -> None:
    """Check a case file (schema, catalogues, topology) and print nodes, edges and circuits."""
    try:
        cs = load_case(case)
        net = build_network(cs.network)
    except Exception as exc:  # noqa: BLE001 - any validation error is reported
        console.print(f"[red]invalid case file {case}:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    _network_summary(cs, net)
    console.print(f"[bold green]{case} is valid[/bold green]")


@app.command()
def show_network(case: Path | None = CaseArg, config: Path | None = ConfigOpt) -> None:
    """Print nodes, edges and the hydraulic circuits (Table 1)."""
    cs = _load(case, config)
    _network_summary(cs, build_network(cs.network))


# --------------------------------------------------------------------------- #
# run / eval / figures
# --------------------------------------------------------------------------- #
@app.command()
def run(
    case: Path | None = CaseArg,
    config: Path | None = ConfigOpt,
    out: Path = typer.Option(
        Path("results"), "--out", "-o", "--results", "-r", help="Result cache directory"
    ),
    solver: str = typer.Option(
        "nlpbb",
        help="Solver back-end: nlpbb (default, NLP branch-and-bound) | bonmin | scip | ipopt | <pyomo solver name>",
    ),
    stages: str = typer.Option(
        ",".join(
            [
                "simulations",
                "no_budget",
                "unlimited",
                "budget_cases",
                "budget_sweep",
                "penalty_sweep",
                "literature",
            ]
        ),
        help="Comma separated stage list",
    ),
    time_limit: float = typer.Option(900.0, help="Time limit per solve [s]"),
    budget_steps: int | None = typer.Option(None, help="Override number of budget sweep steps"),
    penalty_steps: int | None = typer.Option(None, help="Override number of penalty sweep steps"),
    force: bool = typer.Option(False, help="Ignore cached results"),
) -> None:
    """Run every scenario of the paper for one case (cached as JSON in the results directory)."""
    from coolingnet.optimization.solvers import SolverSettings
    from coolingnet.workflow import PaperPipeline, PipelineConfig

    cs = _load(case, config)
    cfg = PipelineConfig(
        results_dir=out,
        solver=SolverSettings(name=solver, time_limit_s=time_limit),
        force=force,
        stages=tuple(s.strip() for s in stages.split(",") if s.strip()),
        budget_steps=budget_steps,
        penalty_steps=penalty_steps,
        progress=lambda msg: console.print(msg),
    )
    PaperPipeline(cs, cfg).run()
    console.print(f"[bold green]done[/bold green] - results in {out}")


@app.command(name="eval")
def eval_(
    case: Path | None = CaseArg,
    config: Path | None = ConfigOpt,
    results: Path = typer.Option(
        Path("results"), "--results", "-r", help="Result cache directory (from `run`)"
    ),
    out: Path = typer.Option(Path("results/eval"), "--out", "-o", help="Report directory"),
) -> None:
    """Compare the cached results with the published tables/figures; write a markdown report and CSVs."""
    from coolingnet.reporting.evaluation import evaluate, write_report

    cs = _load(case, config)
    ev = evaluate(cs, results)
    written = write_report(ev, out)
    t = Table(title="Reproduction of the published values")
    for col in ("item", "values", "max |dev|", "status"):
        t.add_column(col)
    for item, row in ev.summary().iterrows():
        dev = row["max_abs_dev"]
        dev_txt = "" if dev is None or dev != dev else f"{dev:.3g}"
        status = row["status"]
        colour = "green" if status == "reproduced" else "red" if status == "missing" else "yellow"
        t.add_row(str(item), str(row["values"]), dev_txt, f"[{colour}]{status}[/{colour}]")
    console.print(t)
    if ev.missing:
        console.print(
            f"[yellow]missing cached runs for:[/yellow] {', '.join(sorted(set(ev.missing)))}"
        )
    console.print(
        f"[bold green]{len(written)} files written to {out}[/bold green] (report: {out / 'report.md'})"
    )


@app.command()
def figures(
    case: Path | None = CaseArg,
    config: Path | None = ConfigOpt,
    results: Path = typer.Option(Path("results"), "--results", "-r", help="Result cache directory"),
    out: Path = typer.Option(Path("figures"), "--out", "-o", help="Output directory"),
    fmt: str = typer.Option("png", help="png | pdf | svg"),
) -> None:
    """Export every figure and table of the paper from the cached results."""
    import matplotlib

    matplotlib.use("Agg")  # headless rendering (the notebooks keep the inline backend)
    from coolingnet.reporting import export_all

    cs = _load(case, config)
    written = export_all(cs, results, out, fmt=fmt)
    for p in written:
        console.print(f"  {p}")
    console.print(f"[bold green]{len(written)} files written to {out}[/bold green]")


# --------------------------------------------------------------------------- #
# extras
# --------------------------------------------------------------------------- #
@app.command()
def simulate(
    case: Path | None = CaseArg,
    config: Path | None = ConfigOpt,
    hot_flow_factor: float = typer.Option(
        1.0, help="Multiplier of the design hot stream flow rates"
    ),
) -> None:
    """Simulate the existing network (NumPy/SciPy, no optimization); Table 8 with --hot-flow-factor 1.2."""
    from coolingnet.simulation import simulate_design

    cs = _load(case, config)
    r = simulate_design(cs, hot_flow_factor=hot_flow_factor)
    t = Table(
        title=f"Existing network, hot flow x{hot_flow_factor:g} (T_w,in={r.T_w_in_C:.2f} C, T_feed={r.T_w_feed_C:.2f} C)"
    )
    for col in ("tag", "k_kg_s", "T_hot_out_C", "T_hot_out_spec_C", "penalty_USD_y"):
        t.add_column(col, justify="right")
    for tag, row in r.exchangers.items():
        t.add_row(
            tag,
            f"{row['k_kg_s']:.2f}",
            f"{row['T_hot_out_C']:.2f}",
            f"{row['T_hot_out_spec_C']:.2f}",
            f"{row['penalty_USD_y']:.0f}",
        )
    console.print(t)
    console.print(
        f"operating cost {r.operating_cost_USD_y:.1f} USD/y, penalty {r.penalty_USD_y:.1f} USD/y, converged={r.converged}"
    )


@app.command()
def export_config(
    path: Path = typer.Argument(..., help="Destination YAML file"),
    case: Path | None = ConfigOpt,
) -> None:
    """Write a case (default: the paper case) to a YAML file you can edit."""
    p = dump_case(load_case(case), path)
    console.print(f"configuration written to [bold]{p}[/bold]")


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


if __name__ == "__main__":  # pragma: no cover
    app()
