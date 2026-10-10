"""Schematic drawing of the cooling water network (Fig. 1 of the paper)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle

from coolingnet.config.schema import CaseStudy
from coolingnet.network.graph import Network, build_network
from coolingnet.optimization.results import Solution


def _auto_layout(net: Network) -> dict:
    g = nx.DiGraph()
    g.add_nodes_from(net.nodes)
    for e in net.edges:
        g.add_edge(e.tail, e.head)
    # layered layout by longest path from the supply node
    depth = {n: 0 for n in net.nodes}
    for n in nx.topological_sort(g):
        for succ in g.successors(n):
            depth[succ] = max(depth[succ], depth[n] + 1)
    layers: dict[int, list] = {}
    for n, d in depth.items():
        layers.setdefault(d, []).append(n)
    pos = {}
    for d, nodes in layers.items():
        for i, n in enumerate(sorted(nodes, key=str)):
            pos[n] = (float(d), float(i) - (len(nodes) - 1) / 2.0)
    return pos


def plot_network(
    case: CaseStudy,
    solution: Solution | None = None,
    *,
    ax: plt.Axes | None = None,
    show_flows: bool = False,
    title: str | None = None,
) -> plt.Axes:
    """Draw the digraph: pipes as arrows labelled by edge id, pump and coolers as symbols.

    If a `solution` is given, pipe line widths scale with the selected diameter and
    (optionally) flow rates are annotated.
    """
    net = build_network(case.network)
    pos = dict(case.network.layout) if case.network.layout else _auto_layout(net)
    if ax is None:
        _, ax = plt.subplots(figsize=(11, 5))
    diam = solution.pipe_diameters() if solution else {str(p.id): p.diameter_in for p in net.pipes}
    flows = {str(e["id"]): e["k_kg_s"] for e in solution.edges} if solution else {}

    for n in net.nodes:
        x, y = pos[n]
        ax.plot(x, y, "o", color="0.35", ms=4, zorder=3)
    for e in net.edges:
        (x0, y0), (x1, y1) = pos[e.tail], pos[e.head]
        xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
        dx, dy = x1 - x0, y1 - y0
        norm = (dx**2 + dy**2) ** 0.5 or 1.0
        nx_, ny_ = -dy / norm, dx / norm  # unit normal: labels sit beside the edge, not on it
        if ny_ < 0:
            nx_, ny_ = -nx_, -ny_
        if e.kind == "pipe":
            lw = 0.8 + 0.25 * diam[str(e.id)]
            ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=12, lw=lw, color="0.15", shrinkA=4, shrinkB=4, zorder=2))
            text = f"{e.id}"
            if show_flows and flows:
                text += f"\n{flows[str(e.id)]:.1f} kg/s"
            ax.annotate(text, (xm, ym), textcoords="offset points", xytext=(10 * nx_, 10 * ny_ + 2), ha="center", va="center", fontsize=8, color="0.15")
        elif e.kind == "pump":
            ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=12, lw=1.2, color="0.15", shrinkA=4, shrinkB=4, zorder=2))
            ax.add_patch(Circle((xm, ym), 0.13, fc="white", ec="tab:blue", lw=1.5, zorder=4))
            ax.annotate(f"{e.id} (pump)", (xm, ym), textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8, color="tab:blue")
        else:
            ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=12, lw=1.2, color="0.15", shrinkA=4, shrinkB=4, zorder=2))
            ax.add_patch(Circle((xm, ym), 0.22, fc="white", ec="tab:red", lw=1.5, zorder=4))
            ax.plot([xm - 0.22, xm + 0.22], [ym, ym], color="tab:red", lw=1, zorder=5)
            label = e.tag
            if show_flows and flows:
                label += f"\n{flows[str(e.id)]:.1f} kg/s"
            ax.annotate(label, (xm, ym), textcoords="offset points", xytext=(18, 0), ha="left", va="center", fontsize=8, color="tab:red")

    # cooling tower box between the return and the supply nodes
    xs, ys = pos[net.supply_node]
    xr, yr = pos[net.return_node]
    w, h = 0.6, abs(yr - ys) * 0.6
    ax.add_patch(Rectangle((min(xs, xr) - w - 0.25, min(ys, yr) + abs(yr - ys) * 0.2), w, h, fc="0.95", ec="0.3", zorder=1))
    ax.annotate("Cooling\ntower", (min(xs, xr) - w / 2 - 0.25, (ys + yr) / 2), ha="center", va="center", fontsize=8)
    ax.plot([min(xs, xr) - 0.25, xs], [ys, ys], color="0.3", lw=1)
    ax.plot([min(xs, xr) - 0.25, xr], [yr, yr], color="0.3", lw=1)
    ax.annotate("supply", pos[net.supply_node], textcoords="offset points", xytext=(0, -12), ha="center", fontsize=7, color="0.4")
    ax.annotate("return", pos[net.return_node], textcoords="offset points", xytext=(0, 8), ha="center", fontsize=7, color="0.4")

    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.margins(0.12)
    ax.axis("off")
    ax.set_title(title or "Cooling water network (edge ids as in Table 1)", fontsize=10)
    return ax
