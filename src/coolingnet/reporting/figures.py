"""Matplotlib versions of Figs. 2-11 and the animation (Video 1) of the paper."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter

from coolingnet.config.schema import CaseStudy
from coolingnet.optimization.results import Solution

KUSD = 1e-3
STYLE = {
    "original_marker": dict(marker="o", color="black", ms=6, ls="none", label="Original"),
    "new_marker": dict(marker="o", mfc="none", mec="black", ms=10, ls="none", mew=1.2),
}


def _pipe_ids(sol: Solution) -> list[str]:
    return [str(e["id"]) for e in sol.edges if e["kind"] == "pipe"]


# --------------------------------------------------------------------------- #
# Figs. 2, 3, 5, 6, 11 - pipe diameter dot charts
# --------------------------------------------------------------------------- #
def plot_diameter_dotchart(
    case: CaseStudy,
    solution: Solution,
    *,
    ax: plt.Axes | None = None,
    label: str = "Debottlenecked",
    title: str | None = None,
    show_pump: bool = False,
) -> plt.Axes:
    """Original vs. optimized nominal diameters per pipe (arrows show the substitutions)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6.5, 5.5))
    catalogue = [d.nominal_in for d in case.pipes.catalogue]
    original = {str(p.id): p.diameter_in for p in case.network.pipes}
    new = solution.pipe_diameters()
    ids = _pipe_ids(solution)
    y = np.arange(1, len(ids) + 1)
    for d in catalogue:
        ax.axvline(d, color="0.85", lw=0.6, ls=":", zorder=0)
    ax.plot([original[i] for i in ids], y, **STYLE["original_marker"], zorder=3)
    ax.plot([new[i] for i in ids], y, **STYLE["new_marker"], label=label, zorder=4)
    for yi, i in zip(y, ids, strict=True):
        if abs(new[i] - original[i]) > 1e-9:
            ax.annotate(
                "",
                xy=(new[i], yi),
                xytext=(original[i], yi),
                arrowprops=dict(arrowstyle="-|>", color="tab:blue", lw=2.0, shrinkA=3, shrinkB=5),
                zorder=2,
            )
    ax.set_yticks(y)
    ax.set_yticklabels(ids)
    ax.set_ylim(0.3, len(ids) + 0.7)
    ax.set_xlim(0, max(catalogue) * 1.05)
    ax.set_xlabel("Pipe diameter (inches)")
    ax.set_ylabel("Edge index")
    ax.grid(axis="y", color="0.9", lw=0.5)
    ax.legend(loc="upper right", frameon=True)
    if title:
        ax.set_title(title)
    if show_pump:
        pump_txt = ", ".join(
            f"pump {k}: {solution.pump_options()[k]} (was {next(u.option for u in case.network.pumps if str(u.id) == k)})"
            for k in solution.pump_options()
        )
        ax.text(0.02, 0.02, pump_txt, transform=ax.transAxes, fontsize=8, color="tab:blue")
    return ax


# --------------------------------------------------------------------------- #
# Fig. 4 - penalty factor sweep; Figs. 7-8 - budget sweep
# --------------------------------------------------------------------------- #
def _sweep_arrays(
    solutions: Sequence[Solution], key: str
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    sols = [s for s in solutions if s.ok]
    x = (
        np.array(
            [s.spec["budget"] if key == "budget" else s.penalty_factor for s in sols], dtype=float
        )
        * KUSD
    )
    order = np.argsort(x)
    x = x[order]
    cols = {}
    for name in ("cpipe", "cpump", "cope", "cpen", "total_cost"):
        cols[name] = np.array([sols[i].costs[name] for i in order], dtype=float) * KUSD
    cols["capital"] = cols["cpipe"] + cols["cpump"]
    return x, cols


def plot_penalty_sweep(
    solutions: Sequence[Solution],
    *,
    ax: plt.Axes | None = None,
    markers: dict[str, float] | None = None,
    title: str | None = None,
) -> plt.Axes:
    """Fig. 4 - pipe, pump and pipe+pump costs vs. penalty factor (unlimited budget)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6.5, 5))
    x, c = _sweep_arrays(solutions, "penalty")
    ax.step(x, c["capital"], where="post", color="black", lw=2.2, label="Pipe and Pump")
    ax.step(x, c["cpump"], where="post", color="black", lw=1.4, ls="--", label="Pump")
    ax.step(x, c["cpipe"], where="post", color="black", lw=1.4, ls="-.", label="Pipe")
    for name, pen in (markers or {}).items():
        ax.axvline(pen * KUSD, color="0.6", ls=":", lw=1)
        ax.text(
            pen * KUSD,
            ax.get_ylim()[1] * 0.6,
            name,
            rotation=90,
            va="center",
            ha="right",
            fontsize=8,
            color="0.3",
        )
    ax.set_xlabel("Penalty factor (kUSD/(y °C))")
    ax.set_ylabel("Costs (kUSD/y)")
    ax.legend(loc="upper left")
    if title:
        ax.set_title(title)
    return ax


def plot_budget_costs(
    solutions: Sequence[Solution],
    *,
    ax: plt.Axes | None = None,
    current_penalty: float | None = None,
    unlimited: Solution | None = None,
    markers: dict[str, float] | None = None,
    title: str | None = None,
) -> plt.Axes:
    """Fig. 7 - objective function, operating and penalty costs vs. available budget."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6.5, 5))
    x, c = _sweep_arrays(solutions, "budget")
    ax.plot(x, c["total_cost"], color="black", lw=2.0, label="Objective function")
    ax.plot(x, c["cope"], color="tab:green", lw=1.6, ls="--", label="Operational cost")
    ax.plot(x, c["cpen"], color="tab:red", lw=1.6, ls="--", label="Penalty cost")
    if current_penalty is not None:
        ax.axhline(
            current_penalty * KUSD, color="tab:red", lw=1.2, ls="-.", label="Penalty cost (current)"
        )
    y_lo, y_hi = ax.get_ylim()
    if unlimited is not None:
        ax.axvline(unlimited.costs["capital"] * KUSD, color="0.6", ls=":", lw=1)
        ax.text(
            unlimited.costs["capital"] * KUSD,
            y_lo + 0.45 * (y_hi - y_lo),
            "Unlimited budget locus",
            rotation=90,
            fontsize=7,
            va="center",
            ha="right",
            color="0.3",
        )
    for name, b in (markers or {}).items():
        ax.axvline(b * KUSD, color="0.6", ls=":", lw=1)
        ax.text(
            b * KUSD,
            y_lo + 0.45 * (y_hi - y_lo),
            name,
            rotation=90,
            fontsize=7,
            va="center",
            ha="right",
            color="0.3",
        )
    ax.set_xlabel("Available Budget (kUSD/y)")
    ax.set_ylabel("Costs (kUSD/y)")
    ax.legend(loc="center left", fontsize=8)
    if title:
        ax.set_title(title)
    return ax


def plot_budget_interventions(
    solutions: Sequence[Solution],
    *,
    ax: plt.Axes | None = None,
    unlimited: Solution | None = None,
    markers: dict[str, float] | None = None,
    highlight_budget: float | None = None,
    title: str | None = None,
) -> plt.Axes:
    """Fig. 8 - pipe, pump and pipe+pump capital costs vs. available budget (hatched = above budget)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6.5, 5))
    x, c = _sweep_arrays(solutions, "budget")
    xmax = float(x.max()) if len(x) else 1.0
    ymax = max(xmax, float(c["capital"].max()) * 1.05 if len(x) else 1.0)
    ax.fill_between(
        [0, xmax],
        [0, xmax],
        [ymax, ymax],
        facecolor="none",
        hatch="///",
        edgecolor="lightblue",
        lw=0,
    )
    ax.plot([0, xmax], [0, xmax], color="lightblue", lw=1)
    ax.plot(x, c["capital"], color="black", lw=2.2, label="Pipe and Pump")
    ax.plot(x, c["cpump"], color="black", lw=1.4, ls="--", label="Pump")
    ax.plot(x, c["cpipe"], color="black", lw=1.4, ls="-.", label="Pipe")
    if unlimited is not None:
        ax.axvline(unlimited.costs["capital"] * KUSD, color="0.6", ls=":", lw=1)
        ax.text(
            unlimited.costs["capital"] * KUSD,
            ymax * 0.9,
            "Unlimited budget locus",
            rotation=90,
            fontsize=7,
            va="top",
            ha="right",
            color="0.3",
        )
    for name, b in (markers or {}).items():
        ax.axvline(b * KUSD, color="0.6", ls=":", lw=1)
        ax.text(
            b * KUSD,
            ymax * 0.75,
            name,
            rotation=90,
            fontsize=7,
            va="center",
            ha="right",
            color="0.3",
        )
    if highlight_budget is not None:
        ax.axvline(highlight_budget * KUSD, color="tab:blue", ls="--", lw=1.8)
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_xlabel("Available Budget (kUSD/y)")
    ax.set_ylabel("Costs (kUSD/y)")
    ax.legend(loc="upper left")
    if title:
        ax.set_title(title)
    return ax


# --------------------------------------------------------------------------- #
# Figs. 9-10 - comparison bars
# --------------------------------------------------------------------------- #
def plot_comparison_bars(
    solutions: dict[str, Solution],
    *,
    quantity: str = "objective",
    reference_penalty: float | None = None,
    ax: plt.Axes | None = None,
    title: str | None = None,
) -> plt.Axes:
    """Fig. 9 (`quantity='objective'`, kUSD/y) or Fig. 10 (`quantity='penalty_reduction'`, %)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6.5, 4.5))
    names = list(solutions)
    if quantity == "objective":
        vals = [solutions[n].costs["total_cost"] * KUSD for n in names]
        ylabel, fmt = "Objective function (kUSD/y)", "{:.2f}"
    elif quantity == "penalty_reduction":
        if reference_penalty is None:
            raise ValueError("reference_penalty (current condition) is required")
        vals = [
            (reference_penalty - solutions[n].costs["cpen"]) / reference_penalty * 100.0
            for n in names
        ]
        ylabel, fmt = "Penalty reduction (%)", "{:.2f} %"
    else:
        raise ValueError(quantity)
    bars = ax.bar(names, vals, color="0.75", edgecolor="black")
    for b, v in zip(bars, vals, strict=True):
        ax.annotate(
            fmt.format(v),
            (b.get_x() + b.get_width() / 2, b.get_height()),
            textcoords="offset points",
            xytext=(0, 3),
            ha="center",
            fontsize=9,
        )
    ax.set_ylabel(ylabel)
    lo, hi = min(vals), max(vals)
    pad = max(0.15 * (hi - lo), 0.05 * abs(hi), 1e-6)
    ax.set_ylim(max(0, lo - pad) if quantity == "penalty_reduction" else lo - pad, hi + pad)
    if title:
        ax.set_title(title)
    return ax


# --------------------------------------------------------------------------- #
# Video 1 - evolution of the solution with the budget limit
# --------------------------------------------------------------------------- #
def save_budget_animation(
    case: CaseStudy,
    solutions: Sequence[Solution],
    path: str | Path,
    *,
    fps: float = 1.0,
    dpi: int = 90,
) -> Path:
    """Animated GIF: capital costs vs. budget, diameters, pump option and valve head losses per budget."""
    sols = sorted([s for s in solutions if s.ok], key=lambda s: s.spec["budget"])
    fig = plt.figure(figsize=(8, 9))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.2, 0.8])
    ax_cost = fig.add_subplot(gs[0, :])
    ax_dia = fig.add_subplot(gs[1, :])
    ax_pump = fig.add_subplot(gs[2, 0])
    ax_valve = fig.add_subplot(gs[2, 1])
    pump_options = list(case.pumps.options)
    pump_edge = str(case.network.pumps[0].id)
    original_pump = pump_options.index(case.network.pumps[0].option) + 1

    def draw(i: int):
        s = sols[i]
        for ax in (ax_cost, ax_dia, ax_pump, ax_valve):
            ax.clear()
        plot_budget_interventions(
            sols,
            ax=ax_cost,
            highlight_budget=s.spec["budget"],
            title=f"Debottlenecking: B = {s.spec['budget'] * KUSD:.2f} kUSD/y",
        )
        plot_diameter_dotchart(case, s, ax=ax_dia)
        ax_dia.set_title("")
        new_pump = pump_options.index(s.pump_options()[pump_edge]) + 1
        ax_pump.plot([original_pump], [1], **STYLE["original_marker"])
        ax_pump.plot([new_pump], [1], **STYLE["new_marker"])
        if new_pump != original_pump:
            ax_pump.annotate(
                "",
                xy=(new_pump, 1),
                xytext=(original_pump, 1),
                arrowprops=dict(arrowstyle="-|>", color="tab:blue", lw=2),
            )
        ax_pump.set_xlim(0, len(pump_options) + 1)
        ax_pump.set_xticks(range(1, len(pump_options) + 1))
        ax_pump.set_yticks([1])
        ax_pump.set_yticklabels([pump_edge])
        ax_pump.set_xlabel("Pump option")
        valves = [c["valve_head_loss_m"] for c in s.circuits]
        yv = np.arange(1, len(valves) + 1)
        ax_valve.plot(valves, yv, **STYLE["new_marker"])
        ax_valve.hlines(yv, 0, valves, color="tab:blue", lw=2)
        ax_valve.set_yticks(yv)
        ax_valve.set_yticklabels([c["he_tag"] for c in s.circuits])
        ax_valve.set_xlim(
            0, max(1.0, max(max(c["valve_head_loss_m"] for c in q.circuits) for q in sols) * 1.1)
        )
        ax_valve.set_xlabel("Valve head loss (m)")
        fig.tight_layout()

    anim = FuncAnimation(fig, draw, frames=len(sols), interval=1000 / fps)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    anim.save(str(out), writer=PillowWriter(fps=fps), dpi=dpi)
    plt.close(fig)
    return out
