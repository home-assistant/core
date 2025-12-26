"""Constants for the IntelliClima integration."""

from datetime import timedelta
from enum import StrEnum
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "intelliclima"

# Update interval
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)


class FanSpeed(StrEnum):
    """Fan speed options for EcoComfort VMC devices."""

    off = "0"
    sleep = "1"
    low = "2"
    medium = "3"
    high = "4"
    auto = "16"


class FanMode(StrEnum):
    """Fan mode/direction options for EcoComfort VMC devices."""

    off = "0"
    inward = "1"
    outward = "2"
    alternate = "3"
    sensor = "4"
