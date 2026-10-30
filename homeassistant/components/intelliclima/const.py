"""Constants for the IntelliClima integration."""

from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "intelliclima"

# Update interval
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

# Filter status is expensive to compute cloud-side, so it's polled far less often.
FILTER_SCAN_INTERVAL = timedelta(days=1)
