"""Constants for the BSB-LAN integration."""

from datetime import timedelta
from enum import StrEnum
import logging
from typing import Final

# Integration domain
DOMAIN: Final = "bsblan"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=12)  # Legacy interval, kept for compatibility
SCAN_INTERVAL_FAST = timedelta(seconds=12)  # For state/sensor data
SCAN_INTERVAL_SLOW = timedelta(minutes=5)  # For config data

# Services
DATA_BSBLAN_CLIENT: Final = "bsblan_client"

ATTR_INSIDE_TEMPERATURE: Final = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE: Final = "outside_temperature"

CONF_PASSKEY: Final = "passkey"
CONF_HEATING_CIRCUITS: Final = "heating_circuits"

DEFAULT_HEATING_CIRCUITS: Final = (1,)
DEFAULT_PORT: Final = 80

DEFAULT_HOT_WATER_MIN_TEMP: Final = 10.0
DEFAULT_HOT_WATER_MAX_TEMP: Final = 65.0


class Setpoint(StrEnum):
    """Setpoint a temperature change goes to: comfort or nominal, or reduced."""

    NORMAL = "normal"
    REDUCED = "reduced"
