"""Constants for the SensorPush Cloud integration."""

from datetime import timedelta
import logging
from typing import Final

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "sensorpush_cloud"

UPDATE_INTERVAL: Final = timedelta(seconds=60)
MAX_TIME_BETWEEN_UPDATES: Final = UPDATE_INTERVAL * 60
