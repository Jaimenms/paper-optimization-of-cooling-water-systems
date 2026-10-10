"""Physical models shared by the simulator and the optimization model.

All functions accept an `ops` namespace providing `exp`, `log` and `sqrt` so the
same formulas can be evaluated with NumPy (simulation) or used to build Pyomo
expressions (optimization). This keeps a single source of truth for the physics.
"""

from coolingnet.physics.backend import NUMPY_OPS, PYOMO_OPS, MathOps
from coolingnet.physics.cooling_tower import (
    air_enthalpy_operating_line,
    merkel_integral,
    saturated_air_enthalpy,
    tower_characteristic,
)
from coolingnet.physics.heat_exchanger import (
    effectiveness_shell_and_tube,
    film_coefficient,
    heat_capacity_ratio,
    overall_heat_transfer_coefficient,
    overall_u_denominator,
)
from coolingnet.physics.hydraulics import (
    hazen_williams_head_loss,
    heat_exchanger_head_loss,
    pump_head,
    velocity,
)

__all__ = [
    "NUMPY_OPS",
    "PYOMO_OPS",
    "MathOps",
    "air_enthalpy_operating_line",
    "effectiveness_shell_and_tube",
    "film_coefficient",
    "hazen_williams_head_loss",
    "heat_capacity_ratio",
    "heat_exchanger_head_loss",
    "merkel_integral",
    "overall_heat_transfer_coefficient",
    "overall_u_denominator",
    "pump_head",
    "saturated_air_enthalpy",
    "tower_characteristic",
    "velocity",
]
