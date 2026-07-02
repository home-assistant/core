"""Legacy compatibility wrapper for the current default register map.

New code should prefer versioned maps under `register_maps/` and profile
resolution via `profiles.py`.
"""

from .register_maps.types import RegisterDef, SelectRegisterDef
from .register_maps.v22_4_0 import REGISTERS, SELECT_REGISTERS, VALUE_TABLES

__all__ = [
    "REGISTERS",
    "SELECT_REGISTERS",
    "VALUE_TABLES",
    "RegisterDef",
    "SelectRegisterDef",
]
