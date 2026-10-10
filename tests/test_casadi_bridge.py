"""Pyomo -> CasADi translation and the in-process Bonmin / IPOPT solve."""

from __future__ import annotations

import math

import pyomo.environ as pyo
import pytest

from coolingnet.optimization.casadi_bridge import (
    CasadiProblem,
    CasadiTranslationError,
    has_free_discrete,
    max_constraint_violation,
    solve_with_casadi,
    translate,
)


def tiny_model() -> pyo.ConcreteModel:
    """min x + 2y + z  s.t.  exp(x) + 3y >= 5,  z = x^1.852 + sqrt(1 + x^2) + log(x).

    y = 0 forces x >= log 5 (objective ~ 6.39); y = 1 allows x = log 2 (objective ~ 4.05).
    """
    m = pyo.ConcreteModel()
    m.x = pyo.Var(bounds=(0.1, 10.0), initialize=1.0)
    m.y = pyo.Var(domain=pyo.Binary, initialize=0)
    m.z = pyo.Var(initialize=1.0)
    m.c1 = pyo.Constraint(expr=pyo.exp(m.x) + 3 * m.y >= 5)
    m.c2 = pyo.Constraint(expr=m.z == m.x**1.852 + pyo.sqrt(1 + m.x**2) + pyo.log(m.x))
    m.obj = pyo.Objective(expr=m.x + 2 * m.y + m.z, sense=pyo.minimize)
    return m


def test_translate_sizes_and_bounds():
    m = tiny_model()
    prob = translate(m)
    assert isinstance(prob, CasadiProblem)
    assert prob.x.shape == (3, 1)
    assert prob.g.shape == (2, 1)
    assert prob.discrete == [False, True, False]
    assert [v.name for v in prob.variables] == ["x", "y", "z"]
    assert prob.lbx == [0.1, 0.0, -math.inf]
    assert prob.ubx == [10.0, 1.0, math.inf]
    assert prob.lbg == [5.0, 0.0]
    assert prob.ubg == [math.inf, 0.0]
    assert prob.x0 == [1.0, 0.0, 1.0]
    assert [c.name for c in prob.constraints] == ["c1", "c2"]
    assert has_free_discrete(m)


def test_translate_skips_fixed_variables():
    m = tiny_model()
    m.y.fix(1)
    prob = translate(m)
    assert prob.x.shape == (2, 1)
    assert prob.discrete == [False, False]
    assert not has_free_discrete(m)


def test_translate_rejects_two_objectives():
    m = tiny_model()
    m.obj2 = pyo.Objective(expr=m.x)
    with pytest.raises(CasadiTranslationError, match="one active objective"):
        translate(m)


def test_bonmin_solves_tiny_minlp():
    m = tiny_model()
    res = solve_with_casadi(m, "bonmin")
    assert res.success
    assert res.status.upper().startswith("SUCC")
    assert pyo.value(m.y) == 1
    x = pyo.value(m.x)
    assert x == pytest.approx(math.log(2), abs=1e-4)
    assert pyo.value(m.z) == pytest.approx(x**1.852 + math.sqrt(1 + x**2) + math.log(x), abs=1e-6)
    assert res.objective == pytest.approx(x + 2 + pyo.value(m.z), abs=1e-5)
    assert max_constraint_violation(m) == pytest.approx(0.0, abs=1e-6)
    assert res.time_s >= 0.0


def test_ipopt_with_integer_fixed_to_current_value():
    m = tiny_model()
    m.y.set_value(0)
    res = solve_with_casadi(m, "ipopt")
    assert res.success
    # with y fixed at 0 the binding constraint is exp(x) >= 5
    assert pyo.value(m.x) == pytest.approx(math.log(5), abs=1e-4)
    assert max_constraint_violation(m) == pytest.approx(0.0, abs=1e-6)


def test_max_constraint_violation_detects_infeasible_point():
    m = tiny_model()
    m.x.set_value(0.5)
    m.y.set_value(0)
    m.z.set_value(0.0)
    assert max_constraint_violation(m) > 1.0
