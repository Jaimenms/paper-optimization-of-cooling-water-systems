"""Math backends: NumPy for simulation, Pyomo intrinsic functions for modelling."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MathOps:
    exp: Callable[[Any], Any]
    log: Callable[[Any], Any]
    sqrt: Callable[[Any], Any]


NUMPY_OPS = MathOps(exp=np.exp, log=np.log, sqrt=np.sqrt)


def _pyomo_ops() -> MathOps:
    import pyomo.environ as pyo

    return MathOps(exp=pyo.exp, log=pyo.log, sqrt=pyo.sqrt)


class _LazyPyomoOps:
    """Resolve the Pyomo functions on first use (keeps Pyomo import optional)."""

    _ops: MathOps | None = None

    def _get(self) -> MathOps:
        if self._ops is None:
            self._ops = _pyomo_ops()
        return self._ops

    @property
    def exp(self):
        return self._get().exp

    @property
    def log(self):
        return self._get().log

    @property
    def sqrt(self):
        return self._get().sqrt


PYOMO_OPS = _LazyPyomoOps()
