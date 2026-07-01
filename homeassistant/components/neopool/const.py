"""Constants for the NeoPool integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "neopool"
NAME = "NeoPool"

PLATFORMS: list[Platform] = [Platform.SENSOR]

LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = 20  # in seconds
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
CONF_FILTRATION_PUMP_POWER = "filtration_pump_power"

CURRENT_VERSION = 6
