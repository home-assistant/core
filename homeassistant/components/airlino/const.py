"""Constants for the AirLino integration."""

from datetime import timedelta
import logging

from awesomeversion import AwesomeVersion

DOMAIN = "airlino"

MIN_API_VERSION = AwesomeVersion("v19")

UPDATE_INTERVAL = timedelta(seconds=30)

LOGGER = logging.getLogger(__package__)
