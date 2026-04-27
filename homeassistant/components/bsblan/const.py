"""Constants for the BSB-LAN integration."""

from datetime import timedelta
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

ATTR_TARGET_TEMPERATURE: Final = "target_temperature"
ATTR_INSIDE_TEMPERATURE: Final = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE: Final = "outside_temperature"

CONF_PASSKEY: Final = "passkey"
CONF_HEATING_CIRCUITS: Final = "heating_circuits"

DEFAULT_HEATING_CIRCUITS: Final = (1,)
DEFAULT_PORT: Final = 80

HEATING_CIRCUIT_IDENTIFIER_SEPARATOR: Final = "-circuit-"
WATER_HEATER_IDENTIFIER_SUFFIX: Final = "-water-heater"


def heating_circuit_identifier(mac: str, circuit: int) -> str:
    """Return the device identifier for a heating circuit sub-device."""
    return f"{mac}{HEATING_CIRCUIT_IDENTIFIER_SEPARATOR}{circuit}"


def water_heater_identifier(mac: str) -> str:
    """Return the device identifier for the water heater sub-device."""
    return f"{mac}{WATER_HEATER_IDENTIFIER_SUFFIX}"


def circuit_from_identifier(identifier: str) -> int | None:
    """Return the heating circuit number from a sub-device identifier."""
    prefix, separator, suffix = identifier.rpartition(
        HEATING_CIRCUIT_IDENTIFIER_SEPARATOR
    )
    if separator and prefix and suffix.isdigit():
        return int(suffix)
    return None


def is_water_heater_identifier(identifier: str) -> bool:
    """Return whether the device identifier belongs to the water heater."""
    prefix = identifier.removesuffix(WATER_HEATER_IDENTIFIER_SUFFIX)
    return bool(prefix) and prefix != identifier
