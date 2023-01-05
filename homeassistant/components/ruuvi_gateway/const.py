"""Constants for the Ruuvi Gateway integration."""
from datetime import timedelta

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)

DOMAIN = "ruuvi_gateway"
SCAN_INTERVAL = timedelta(seconds=5)
OLD_ADVERTISEMENT_CUTOFF = timedelta(
    seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
)
