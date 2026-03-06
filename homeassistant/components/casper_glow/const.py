"""Constants for the Casper Glow integration."""

from datetime import timedelta

from pycasperglow import BRIGHTNESS_LEVELS, DEVICE_NAME_PREFIX, DIMMING_TIME_MINUTES

DOMAIN = "casper_glow"

LOCAL_NAMES = {DEVICE_NAME_PREFIX}

# Map device brightness percentages (60-100) to HA's 0-255 scale.
# The device only supports 5 fixed levels, so we spread them evenly
# across HA's 1-255 range (0 is reserved for off) rather than
# mapping them proportionally, which would cluster all steps in the
# top 40% of the slider.
_LEVELS = sorted(BRIGHTNESS_LEVELS)
BRIGHTNESS_PCT_TO_HA: dict[int, int] = {
    pct: round(1 + (i / (len(_LEVELS) - 1)) * 254) for i, pct in enumerate(_LEVELS)
}

DEFAULT_DIMMING_TIME_MINUTES: int = DIMMING_TIME_MINUTES[0]

# Interval between periodic state polls to catch externally-triggered changes.
STATE_POLL_INTERVAL = timedelta(seconds=30)
