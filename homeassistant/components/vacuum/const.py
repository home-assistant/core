"""Support for vacuum cleaner robots (botvacs)."""

from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .entity import StateVacuumEntity

DOMAIN: Final = "vacuum"

ATTR_FAN_SPEED: Final = "fan_speed"
ATTR_PARAMS: Final = "params"

SERVICE_CLEAN_AREA: Final = "clean_area"
SERVICE_CLEAN_SPOT: Final = "clean_spot"
SERVICE_LOCATE: Final = "locate"
SERVICE_PAUSE: Final = "pause"
SERVICE_RETURN_TO_BASE: Final = "return_to_base"
SERVICE_SEND_COMMAND: Final = "send_command"
SERVICE_SET_FAN_SPEED: Final = "set_fan_speed"
SERVICE_START: Final = "start"
SERVICE_STOP: Final = "stop"

DATA_COMPONENT: HassKey[EntityComponent[StateVacuumEntity]] = HassKey(DOMAIN)

ISSUE_SEGMENTS_CHANGED = "segments_changed"


class VacuumActivity(StrEnum):
    """Vacuum activity states."""

    CLEANING = "cleaning"
    DOCKED = "docked"
    IDLE = "idle"
    PAUSED = "paused"
    RETURNING = "returning"
    ERROR = "error"


class VacuumEntityCapabilityAttribute(StrEnum):
    """Capability attributes for vacuum devices."""

    FAN_SPEED_LIST = "fan_speed_list"


class VacuumEntityStateAttribute(StrEnum):
    """State attributes for vacuum entities."""

    FAN_SPEED = "fan_speed"


class VacuumEntityFeature(IntFlag):
    """Supported features of the vacuum entity."""

    TURN_ON = 1  # Deprecated, not supported by StateVacuumEntity
    TURN_OFF = 2  # Deprecated, not supported by StateVacuumEntity
    PAUSE = 4
    STOP = 8
    RETURN_HOME = 16
    FAN_SPEED = 32
    STATUS = 128  # Deprecated, not supported by StateVacuumEntity
    SEND_COMMAND = 256
    LOCATE = 512
    CLEAN_SPOT = 1024
    MAP = 2048
    STATE = 4096  # Must be set by vacuum platforms derived from StateVacuumEntity
    START = 8192
    CLEAN_AREA = 16384


class VacuumService(StrEnum):
    """Store keys for vacuum services."""

    CLEAN_AREA = "clean_area"
    CLEAN_SPOT = "clean_spot"
    LOCATE = "locate"
    PAUSE = "pause"
    RETURN_TO_BASE = "return_to_base"
    SEND_COMMAND = "send_command"
    SET_FAN_SPEED = "set_fan_speed"
    START = "start"
    STOP = "stop"


class VacuumServiceArgument(StrEnum):
    """Store keys for vacuum service arguments."""

    CLEANING_AREA_ID = "cleaning_area_id"
    COMMAND = "command"
    FAN_SPEED = "fan_speed"
    PARAMS = "params"
