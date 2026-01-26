"""Support for vacuum cleaner robots (botvacs)."""

from __future__ import annotations

from enum import IntFlag, StrEnum
from functools import partial
from typing import TYPE_CHECKING

from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import StateVacuumEntity

DOMAIN = "vacuum"

DATA_COMPONENT: HassKey[EntityComponent[StateVacuumEntity]] = HassKey(DOMAIN)


class VacuumActivity(StrEnum):
    """Vacuum activity states."""

    CLEANING = "cleaning"
    DOCKED = "docked"
    IDLE = "idle"
    PAUSED = "paused"
    RETURNING = "returning"
    ERROR = "error"


class VacuumEntityFeature(IntFlag):
    """Supported features of the vacuum entity."""

    TURN_ON = 1  # Deprecated, not supported by StateVacuumEntity
    TURN_OFF = 2  # Deprecated, not supported by StateVacuumEntity
    PAUSE = 4
    STOP = 8
    RETURN_HOME = 16
    FAN_SPEED = 32
    BATTERY = 64
    STATUS = 128  # Deprecated, not supported by StateVacuumEntity
    SEND_COMMAND = 256
    LOCATE = 512
    CLEAN_SPOT = 1024
    MAP = 2048
    STATE = 4096  # Must be set by vacuum platforms derived from StateVacuumEntity
    START = 8192


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
