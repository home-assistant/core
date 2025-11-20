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

# Default lists for vacuum capabilities
DEFAULT_CLEANING_MODES = ["Vacuuming", "Mopping", "Vacuuming and mopping"]
DEFAULT_WATER_LEVELS = ["Slightly dry", "Moist", "Wet"]


class VacuumActivity(StrEnum):
    """Vacuum activity states."""

    AUTO_EMPTYING = "auto_emptying"
    CLEANING = "cleaning"
    CLEANING_MOPS = "cleaning_mop_pads"
    DOCKED = "docked"
    DRYING_MOPS = "drying_mop_pads"
    ERROR = "error"
    IDLE = "idle"
    MOPPING = "mopping"
    PAUSED = "paused"
    RETURNING = "returning"
    VACUUMING = "vacuuming"
    VACUUMING_AND_MOPPING = "vacuuming_and_mopping"


# These STATE_* constants are deprecated as of Home Assistant 2025.1.
# Please use the VacuumActivity enum instead.
_DEPRECATED_STATE_AUTO_EMPTYING = DeprecatedConstantEnum(
    VacuumActivity.AUTO_EMPTYING, "2026.1"
)
_DEPRECATED_STATE_CLEANING = DeprecatedConstantEnum(VacuumActivity.CLEANING, "2026.1")
_DEPRECATED_STATE_CLEANING_MOPS = DeprecatedConstantEnum(
    VacuumActivity.CLEANING_MOPS, "2026.1"
)
_DEPRECATED_STATE_DOCKED = DeprecatedConstantEnum(VacuumActivity.DOCKED, "2026.1")
_DEPRECATED_STATE_DRYING_MOPS = DeprecatedConstantEnum(
    VacuumActivity.DRYING_MOPS, "2026.1"
)
_DEPRECATED_STATE_ERROR = DeprecatedConstantEnum(VacuumActivity.ERROR, "2026.1")
_DEPRECATED_STATE_MOPPING = DeprecatedConstantEnum(VacuumActivity.MOPPING, "2026.1")
_DEPRECATED_STATE_RETURNING = DeprecatedConstantEnum(VacuumActivity.RETURNING, "2026.1")
_DEPRECATED_STATE_VACUUMING = DeprecatedConstantEnum(VacuumActivity.VACUUMING, "2026.1")
_DEPRECATED_STATE_VACUUMING_AND_MOPPING = DeprecatedConstantEnum(
    VacuumActivity.VACUUMING_AND_MOPPING, "2026.1"
)


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
