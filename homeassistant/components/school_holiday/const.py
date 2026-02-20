"""Constants for the School Holidays integration."""

from __future__ import annotations

from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

CONF_CALENDAR_NAME = "calendar_name"
CONF_SENSOR_NAME = "sensor_name"
COUNTRIES = ["The Netherlands"]
DEFAULT_CALENDAR_NAME = "School Holiday Calendar"
DEFAULT_SENSOR_NAME = "School Holiday Sensor"
DOMAIN = "school_holiday"
INTEGRATION_NAME = "School Holiday"
REGIONS = {"The Netherlands": ["Midden", "Noord", "Zuid"]}
SCAN_INTERVAL = timedelta(hours=1)
