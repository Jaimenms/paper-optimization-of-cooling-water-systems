"""Network structure: incidence matrix M (Eq. 1) and hydraulic circuit matrix Λ (Eq. 3).

The elements of the system are represented by a digraph (Section 2.1 of the
paper). Edges are pipes, pumps and heat exchangers; nodes are the tower basin
(supply), the tower top (return) and interconnections. A *hydraulic circuit* is
the path from the supply node to the return node through one heat exchanger;
each heat exchanger must belong to exactly one circuit (parallel alignment).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from coolingnet.config.schema import (
    Edge,
    EdgeId,
    HeatExchangerEdge,
    NetworkConfig,
    NodeId,
    PipeEdge,
    PumpEdge,
)


class NetworkStructureError(ValueError):
    """Raised when the digraph does not satisfy the model assumptions."""


@dataclass(frozen=True)
class Circuit:
    """Ordered list of edge ids from the supply node to the return node through `he_edge`."""

    index: int
    he_edge: EdgeId
    he_tag: str
    edge_ids: tuple[EdgeId, ...]


@dataclass(frozen=True)
class Network:
    nodes: tuple[NodeId, ...]
    edges: tuple[Edge, ...]
    supply_node: NodeId
    return_node: NodeId
    elevation_difference_m: float
    incidence: np.ndarray = field(repr=False)  # M[t, k]: +1 enters node t, -1 leaves node t
    circuits: tuple[Circuit, ...]
    circuit_matrix: np.ndarray = field(repr=False)  # Λ[l, k]: 1 if edge k belongs to circuit l

    # --- indexing -------------------------------------------------------------
    @property
    def edge_ids(self) -> list[EdgeId]:
        return [e.id for e in self.edges]

    def edge(self, edge_id: EdgeId) -> Edge:
        return self.edges[self.edge_index(edge_id)]

    def edge_index(self, edge_id: EdgeId) -> int:
        return self.edge_ids.index(edge_id)

    def node_index(self, node: NodeId) -> int:
        return self.nodes.index(node)

    @property
    def pipes(self) -> list[PipeEdge]:
        return [e for e in self.edges if isinstance(e, PipeEdge)]

    @property
    def pumps(self) -> list[PumpEdge]:
        return [e for e in self.edges if isinstance(e, PumpEdge)]

    @property
    def heat_exchangers(self) -> list[HeatExchangerEdge]:
        return [e for e in self.edges if isinstance(e, HeatExchangerEdge)]

    @property
    def interconnection_nodes(self) -> list[NodeId]:
        return [n for n in self.nodes if n not in (self.supply_node, self.return_node)]

    def circuit_of(self, he_edge: EdgeId) -> Circuit:
        return next(c for c in self.circuits if c.he_edge == he_edge)

    def circuits_containing(self, edge_id: EdgeId) -> list[Circuit]:
        return [c for c in self.circuits if edge_id in c.edge_ids]

    def label(self, edge_id: EdgeId) -> str:
        return self.edge(edge_id).label

    # --- exports ---------------------------------------------------------------
    def circuit_table(self) -> list[dict[str, object]]:
        """Rows of Table 1 of the paper: circuit index and its labelled edges."""
        return [
            {"Circuit": c.index, "Edges": ", ".join(self.label(e) for e in c.edge_ids)}
            for c in self.circuits
        ]

    def to_networkx(self) -> nx.MultiDiGraph:
        g = nx.MultiDiGraph()
        g.add_nodes_from(self.nodes)
        for e in self.edges:
            g.add_edge(e.tail, e.head, key=e.id, kind=e.kind, label=e.label)
        return g


def _incidence_matrix(nodes: list[NodeId], edges: list[Edge]) -> np.ndarray:
    m = np.zeros((len(nodes), len(edges)), dtype=int)
    for k, e in enumerate(edges):
        m[nodes.index(e.head), k] = +1
        m[nodes.index(e.tail), k] = -1
    return m


def _unique_edge_path(
    g: nx.MultiDiGraph, source: NodeId, target: NodeId, what: str
) -> list[EdgeId]:
    if source == target:
        return []
    paths = list(nx.all_simple_edge_paths(g, source, target))
    if len(paths) == 0:
        raise NetworkStructureError(f"no path {what}: node {source} -> node {target}")
    if len(paths) > 1:
        raise NetworkStructureError(
            f"{len(paths)} alternative paths {what} (node {source} -> node {target}); "
            "the model assumes coolers in parallel, each one in a single hydraulic circuit"
        )
    return [key for (_u, _v, key) in paths[0]]


def build_network(config: NetworkConfig) -> Network:
    """Build the incidence matrix and derive the hydraulic circuits of a configuration."""
    edges = list(config.edges)
    nodes: list[NodeId] = []
    for e in edges:
        for n in (e.tail, e.head):
            if n not in nodes:
                nodes.append(n)
    for special, name in ((config.supply_node, "supply"), (config.return_node, "return")):
        if special not in nodes:
            raise NetworkStructureError(f"{name} node {special} is not connected to any edge")
    g = nx.MultiDiGraph()
    g.add_nodes_from(nodes)
    for e in edges:
        g.add_edge(e.tail, e.head, key=e.id)

    if g.in_degree(config.supply_node) != 0:
        raise NetworkStructureError("the supply node must not have incoming edges")
    if g.out_degree(config.return_node) != 0:
        raise NetworkStructureError("the return node must not have outgoing edges")
    if not nx.is_weakly_connected(g):
        raise NetworkStructureError("the network is not connected")

    circuits: list[Circuit] = []
    for idx, he in enumerate((e for e in edges if isinstance(e, HeatExchangerEdge)), start=1):
        upstream = _unique_edge_path(g, config.supply_node, he.tail, f"upstream of {he.tag}")
        downstream = _unique_edge_path(g, he.head, config.return_node, f"downstream of {he.tag}")
        path = (*upstream, he.id, *downstream)
        for eid in path:
            if isinstance(
                config_edge := edges[[e.id for e in edges].index(eid)], HeatExchangerEdge
            ):
                if config_edge.id != he.id:
                    raise NetworkStructureError(
                        f"circuit of {he.tag} passes through {config_edge.tag}: "
                        "coolers in series are not supported"
                    )
        circuits.append(Circuit(index=idx, he_edge=he.id, he_tag=he.tag, edge_ids=path))

    edge_ids = [e.id for e in edges]
    lam = np.zeros((len(circuits), len(edges)), dtype=int)
    for c in circuits:
        for eid in c.edge_ids:
            lam[c.index - 1, edge_ids.index(eid)] = 1
    orphans = [edge_ids[k] for k in range(len(edges)) if lam[:, k].sum() == 0]
    if orphans:
        raise NetworkStructureError(f"edges {orphans} do not belong to any hydraulic circuit")

    return Network(
        nodes=tuple(nodes),
        edges=tuple(edges),
        supply_node=config.supply_node,
        return_node=config.return_node,
        elevation_difference_m=config.elevation_difference_m,
        incidence=_incidence_matrix(nodes, edges),
        circuits=tuple(circuits),
        circuit_matrix=lam,
    )
