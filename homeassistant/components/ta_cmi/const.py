"""Constants for the Technische Alternative C.M.I. integration."""

from datetime import timedelta
from logging import Logger, getLogger
from typing import Dict

_LOGGER: Logger = getLogger(__package__)

SCAN_INTERVAL: timedelta = timedelta(minutes=5)

DOMAIN: str = "ta_cmi"

CONF_DEVICES: str = "devices"
CONF_DEVICE_ID: str = "id"
CONF_DEVICE_FETCH_MODE: str = "fetchmode"

CONF_CHANNELS: str = "channels"
CONF_CHANNELS_TYPE: str = "type"
CONF_CHANNELS_ID: str = "id"
CONF_CHANNELS_NAME: str = "name"
CONF_CHANNELS_DEVICE_CLASS: str = "device_class"

DEFAULT_DEVICE_CLASS_MAP: Dict[str, str] = {
    "°C": "temperature",
    "K": "temperature",
    "A": "current",
    "kWh": "energy",
    "m³": "gas",
    "%": "humidity",
    "lx": "illuminance",
    "W": "power",
    "mbar": "pressure",
    "V": "voltage",
}
