"""Comelit constants."""

import logging

from aiocomelit.const import BRIDGE, VEDO

_LOGGER = logging.getLogger(__package__)

DOMAIN = "comelit"
DEFAULT_PORT = 80
DEVICE_TYPE_LIST = [BRIDGE, VEDO]

SCAN_INTERVAL = 5

PRESET_MODE_AUTO = "Automatic"
PRESET_MODE_MANUAL = "Manual"

PRESET_MODE_AUTO_TARGET_TEMP = 20
