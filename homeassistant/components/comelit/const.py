"""Comelit constants."""

import logging

from aiocomelit.api import (
    ComelitSerialBridgeObject,
    ComelitVedoAreaObject,
    ComelitVedoZoneObject,
)
from aiocomelit.const import BRIDGE, VEDO

_LOGGER = logging.getLogger(__package__)

ObjectClassType = (
    ComelitSerialBridgeObject | ComelitVedoAreaObject | ComelitVedoZoneObject
)


DOMAIN = "comelit"
DEFAULT_PORT = 80
DEVICE_TYPE_LIST = [BRIDGE, VEDO]
CONF_VEDO_PIN = "vedo_pin"

SCAN_INTERVAL = 5

PRESET_MODE_AUTO = "automatic"
PRESET_MODE_MANUAL = "manual"

PRESET_MODE_AUTO_TARGET_TEMP = 20
