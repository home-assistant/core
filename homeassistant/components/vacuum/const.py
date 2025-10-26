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


class VacuumActivity(StrEnum):
    """Vacuum activity states."""

    CLEANING = "cleaning"
    DOCKED = "docked"
    IDLE = "idle"
    PAUSED = "paused"
    RETURNING = "returning"
    ERROR = "error"


# These STATE_* constants are deprecated as of Home Assistant 2025.1.
# Please use the VacuumActivity enum instead.
_DEPRECATED_STATE_CLEANING = DeprecatedConstantEnum(VacuumActivity.CLEANING, "2026.1")
_DEPRECATED_STATE_DOCKED = DeprecatedConstantEnum(VacuumActivity.DOCKED, "2026.1")
_DEPRECATED_STATE_RETURNING = DeprecatedConstantEnum(VacuumActivity.RETURNING, "2026.1")
_DEPRECATED_STATE_ERROR = DeprecatedConstantEnum(VacuumActivity.ERROR, "2026.1")


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
