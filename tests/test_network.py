"""Digraph, incidence matrix (Eq. 1) and hydraulic circuits (Eq. 3, Table 1)."""

from __future__ import annotations

import numpy as np
import pytest

from coolingnet import build_network
from coolingnet.config.schema import NetworkConfig
from coolingnet.network import NetworkStructureError

TABLE_1 = {
    1: "1, 2, 3, 9, E-101, 14, 8",
    2: "1, 2, 3, 10, E-102, 15, 8",
    3: "1, 2, 3, 4, 11, E-103, 16, 7, 8",
    4: "1, 2, 3, 4, 5, 12, E-104, 17, 6, 7, 8",
    5: "1, 2, 3, 4, 5, 13, E-105, 18, 6, 7, 8",
}


def test_sizes(network):
    assert len(network.nodes) == 20
    assert len(network.edges) == 23
    assert len(network.circuits) == 5
    assert len(network.pipes) == 17
    assert len(network.pumps) == 1
    assert len(network.heat_exchangers) == 5
    assert len(network.interconnection_nodes) == 18


def test_circuit_table_matches_table_1(network):
    rows = network.circuit_table()
    assert {r["Circuit"]: r["Edges"] for r in rows} == TABLE_1


def test_circuit_objects(network):
    c3 = network.circuit_of(21)
    assert c3.index == 3
    assert c3.he_tag == "E-103"
    assert c3.edge_ids == (1, 2, 3, 4, 11, 21, 16, 7, 8)
    # the supply header and the pump belong to every circuit
    assert [c.index for c in network.circuits_containing(2)] == [1, 2, 3, 4, 5]
    assert [c.index for c in network.circuits_containing(5)] == [4, 5]


def test_incidence_matrix(network):
    m = network.incidence
    assert m.shape == (20, 23)
    assert np.all(m.sum(axis=0) == 0)
    assert set(np.unique(m)) == {-1, 0, 1}
    # pipe 1 goes from the supply node 1 to node 2
    k = network.edge_index(1)
    assert m[network.node_index(1), k] == -1
    assert m[network.node_index(2), k] == +1
    # supply node has only outgoing edges, return node only incoming ones
    assert np.all(m[network.node_index(network.supply_node)] <= 0)
    assert np.all(m[network.node_index(network.return_node)] >= 0)


def test_circuit_matrix(network):
    lam = network.circuit_matrix
    assert lam.shape == (5, 23)
    assert np.all(lam.sum(axis=0) >= 1)
    assert set(np.unique(lam)) <= {0, 1}
    # each heat exchanger belongs to exactly one circuit
    for he in network.heat_exchangers:
        assert lam[:, network.edge_index(he.id)].sum() == 1
    # the pump belongs to all circuits
    assert lam[:, network.edge_index(2)].sum() == 5


def test_networkx_export(network):
    g = network.to_networkx()
    assert g.number_of_nodes() == 20
    assert g.number_of_edges() == 23


def _cfg(edges, supply=1, ret=4):
    return NetworkConfig(
        supply_node=supply, return_node=ret, elevation_difference_m=0.0, edges=edges
    )


def test_parallel_paths_to_a_cooler_raise():
    cfg = _cfg(
        [
            {"id": 1, "kind": "pipe", "tail": 1, "head": 2, "length_m": 10, "diameter_in": 10},
            {"id": 2, "kind": "pipe", "tail": 1, "head": 2, "length_m": 10, "diameter_in": 10},
            {"id": 3, "kind": "pump", "tail": 2, "head": 3, "option": "1"},
            {"id": 4, "kind": "heat_exchanger", "tail": 3, "head": 4, "tag": "E-1"},
        ]
    )
    with pytest.raises(NetworkStructureError, match="alternative paths"):
        build_network(cfg)


def test_disconnected_network_raises():
    cfg = _cfg(
        [
            {"id": 1, "kind": "pipe", "tail": 1, "head": 2, "length_m": 10, "diameter_in": 10},
            {"id": 3, "kind": "pump", "tail": 2, "head": 3, "option": "1"},
            {"id": 4, "kind": "heat_exchanger", "tail": 3, "head": 4, "tag": "E-1"},
            {"id": 5, "kind": "pipe", "tail": 7, "head": 8, "length_m": 10, "diameter_in": 10},
        ]
    )
    with pytest.raises(NetworkStructureError, match="not connected"):
        build_network(cfg)


def test_coolers_in_series_raise():
    cfg = _cfg(
        [
            {"id": 1, "kind": "pipe", "tail": 1, "head": 2, "length_m": 10, "diameter_in": 10},
            {"id": 2, "kind": "pump", "tail": 2, "head": 3, "option": "1"},
            {"id": 3, "kind": "heat_exchanger", "tail": 3, "head": 5, "tag": "E-1"},
            {"id": 4, "kind": "heat_exchanger", "tail": 5, "head": 4, "tag": "E-2"},
        ]
    )
    with pytest.raises(NetworkStructureError, match="series"):
        build_network(cfg)


def test_minimal_valid_network_builds():
    cfg = _cfg(
        [
            {"id": 1, "kind": "pipe", "tail": 1, "head": 2, "length_m": 10, "diameter_in": 10},
            {"id": 2, "kind": "pump", "tail": 2, "head": 3, "option": "1"},
            {"id": 3, "kind": "heat_exchanger", "tail": 3, "head": 4, "tag": "E-1"},
        ]
    )
    net = build_network(cfg)
    assert net.circuit_table() == [{"Circuit": 1, "Edges": "1, 2, E-1"}]
    assert net.incidence.shape == (4, 3)
