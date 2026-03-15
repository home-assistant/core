"""Constants for the Casper Glow integration."""

from datetime import timedelta

from pycasperglow import BRIGHTNESS_LEVELS, DEVICE_NAME_PREFIX, DIMMING_TIME_MINUTES

DOMAIN = "casper_glow"

LOCAL_NAMES = {DEVICE_NAME_PREFIX}

SORTED_BRIGHTNESS_LEVELS = sorted(BRIGHTNESS_LEVELS)

DEFAULT_DIMMING_TIME_MINUTES: int = DIMMING_TIME_MINUTES[0]

# Interval between periodic state polls to catch externally-triggered changes.
STATE_POLL_INTERVAL = timedelta(seconds=30)
