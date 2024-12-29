"""Constants for the SensorPush Cloud integration."""

from datetime import timedelta
import logging
from typing import Final

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "sensorpush_cloud"

ATTR_ALTITUDE: Final = "altitude"
ATTR_ATMOSPHERIC_PRESSURE: Final = "atmospheric_pressure"
ATTR_BATTERY_VOLTAGE: Final = "battery_voltage"
ATTR_DEWPOINT: Final = "dewpoint"
ATTR_HUMIDITY: Final = "humidity"
ATTR_LAST_UPDATE: Final = "last_update"
ATTR_SIGNAL_STRENGTH: Final = "signal_strength"
ATTR_VAPOR_PRESSURE: Final = "vapor_pressure"

UPDATE_INTERVAL: Final = timedelta(seconds=60)
MAX_TIME_BETWEEN_UPDATES: Final = UPDATE_INTERVAL * 60
