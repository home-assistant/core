"""Support for vacuum cleaner robots (botvacs)."""

from __future__ import annotations

from enum import StrEnum
from functools import partial

from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

DOMAIN = "vacuum"


class VacuumState(StrEnum):
    """Vacuum entity states."""

    CLEANING = "cleaning"
    DOCKED = "docked"
    IDLE = "idle"
    PAUSED = "paused"
    RETURNING = "returning"
    ERROR = "error"


# These STATE_* constants are deprecated as of Home Assistant 2024.11.
# Please use the VacuumState enum instead.
_DEPRECATED_STATE_CLEANING = DeprecatedConstantEnum(VacuumState.CLEANING, "2025.11")
_DEPRECATED_STATE_DOCKED = DeprecatedConstantEnum(VacuumState.DOCKED, "2025.11")
_DEPRECATED_STATE_RETURNING = DeprecatedConstantEnum(VacuumState.RETURNING, "2025.11")
_DEPRECATED_STATE_ERROR = DeprecatedConstantEnum(VacuumState.ERROR, "2025.11")


STATES = [cls.value for cls in VacuumState]

# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
