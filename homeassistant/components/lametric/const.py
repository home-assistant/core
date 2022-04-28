"""Constants for the LaMetric integration."""

import logging
from typing import Final

DOMAIN: Final = "lametric"

LOGGER = logging.getLogger(__package__)

AVAILABLE_PRIORITIES: Final = ["info", "warning", "critical"]
AVAILABLE_ICON_TYPES: Final = ["none", "info", "alert"]

CONF_CYCLES: Final = "cycles"
CONF_LIFETIME: Final = "lifetime"
CONF_PRIORITY: Final = "priority"
CONF_ICON_TYPE: Final = "icon_type"
