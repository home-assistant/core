"""Constants for the Efergy integration."""
from datetime import timedelta
import logging
from typing import Final

CONF_CURRENT_VALUES = "current_values"

DEFAULT_NAME = "Efergy"
DOMAIN: Final = "efergy"

LOGGER = logging.getLogger(__package__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)
