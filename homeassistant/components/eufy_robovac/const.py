"""Constants for the Eufy RoboVac integration."""

from enum import StrEnum
from typing import Any, TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

DOMAIN = "eufy_robovac"
PLATFORMS: list[Platform] = [Platform.VACUUM, Platform.SENSOR]

CONF_LOCAL_KEY = "local_key"
CONF_PROTOCOL_VERSION = "protocol_version"
DEFAULT_PROTOCOL_VERSION = "3.3"


def dps_update_signal(entry_id: str) -> str:
    """Build dispatcher signal name for DPS updates."""
    return f"{DOMAIN}_{entry_id}_dps_updated"


class EufyRoboVacRuntimeData(TypedDict):
    """Runtime data for a Eufy RoboVac config entry."""

    dps: dict[str, Any]


type EufyRoboVacConfigEntry = ConfigEntry[EufyRoboVacRuntimeData]


class RoboVacCommand(StrEnum):
    """Canonical command names for model mappings."""

    START_PAUSE = "start_pause"
    DIRECTION = "direction"
    MODE = "mode"
    STATUS = "status"
    RETURN_HOME = "return_home"
    FAN_SPEED = "fan_speed"
    LOCATE = "locate"
    BATTERY = "battery"
    ERROR = "error"
