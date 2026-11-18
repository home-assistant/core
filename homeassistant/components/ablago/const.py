"""Constants for the Ablago integration."""

from datetime import timedelta
import logging

DOMAIN = "ablago"

LOGGER = logging.getLogger(__package__)

# Ablago answers unchanged counters with 304 and no body, so polling once a minute costs next to nothing.
UPDATE_INTERVAL_COUNTERS = timedelta(minutes=1)
UPDATE_INTERVAL_HEALTH = timedelta(minutes=1)
