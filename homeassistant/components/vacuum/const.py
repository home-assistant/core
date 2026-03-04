"""Support for vacuum cleaner robots (botvacs)."""

from __future__ import annotations

from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING

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
    CLEAN_AREA = 16384
