"""Constants for the LaMetric integration."""

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "lametric"
PLATFORMS = [Platform.BUTTON, Platform.NUMBER]

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=30)

CONF_CYCLES: Final = "cycles"
CONF_ICON_TYPE: Final = "icon_type"
CONF_LIFETIME: Final = "lifetime"
CONF_PRIORITY: Final = "priority"
CONF_SOUND: Final = "sound"
