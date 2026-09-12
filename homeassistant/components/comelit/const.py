"""Comelit constants."""

import logging

from aiocomelit.api import (
    ComelitSerialBridgeObject,
    ComelitVedoAreaObject,
    ComelitVedoZoneObject,
)
from aiocomelit.const import BRIDGE, VEDO

LOGGER = logging.getLogger(__package__)

type ObjectClassType = (
    ComelitSerialBridgeObject | ComelitVedoAreaObject | ComelitVedoZoneObject
)


DOMAIN = "comelit"
DEFAULT_PORT = 80
DEVICE_TYPE_LIST = [BRIDGE, VEDO]
CONF_VEDO_PIN = "vedo_pin"

SCAN_INTERVAL = 5

CONF_TRAVEL_TIME = "travel_time"
DEFAULT_COVER_TRAVEL_TIME = 25
MIN_COVER_TRAVEL_TIME = 1
MAX_COVER_TRAVEL_TIME = 120

PRESET_MODE_AUTO = "automatic"
PRESET_MODE_MANUAL = "manual"

PRESET_MODE_AUTO_TARGET_TEMP = 20
