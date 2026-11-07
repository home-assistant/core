"""Constants for the Tank Utility integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "tank_utility"
LOGGER = logging.getLogger(__package__)

PLATFORMS: list[Platform] = [Platform.SENSOR]
