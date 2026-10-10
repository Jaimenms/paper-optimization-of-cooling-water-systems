"""Shared fixtures: the paper case study and its network (both immutable, built once)."""

from __future__ import annotations

import pytest

import coolingnet
from coolingnet import build_network

TAGS = ["E-101", "E-102", "E-103", "E-104", "E-105"]


@pytest.fixture(scope="session")
def case():
    """The paper's case study (frozen pydantic model, safe to share between tests)."""
    return coolingnet.load_case()


@pytest.fixture(scope="session")
def network(case):
    return build_network(case.network)


@pytest.fixture(scope="session")
def tags():
    """Heat exchanger tags in the order of the paper's tables."""
    return list(TAGS)
