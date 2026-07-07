"""Constants for the Mitsubishi Comfort integration."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "mitsubishi_comfort"
PLATFORMS: Final = [Platform.CLIMATE]

# Config entry data key holding the per-device LAN address cache, keyed by the
# device's formatted MAC. The cloud API only returns each device's MAC, never
# its LAN IP, so addresses are resolved from DHCP discovery and persisted here
# to survive restarts without re-discovery.
CONF_ADDRESSES: Final = "addresses"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_CONNECT_TIMEOUT: Final = 1.2
DEFAULT_RESPONSE_TIMEOUT: Final = 8.0
