"""Constants for the Mitsubishi Comfort integration."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "mitsubishi_comfort"
PLATFORMS: Final = [Platform.CLIMATE]

# Config entry data key holding the per-device LAN address cache, keyed by the
# device's formatted MAC. The cloud API only returns each device's MAC, never
# its LAN IP, so addresses come from DHCP discovery and from manual entry in the
# options flow, then persisted here to survive restarts.
CONF_ADDRESSES: Final = "addresses"

# Config entry data key holding per-device credentials (the Socket.IO-fetched
# password, plus the cryptoSerial and MAC read from the device status endpoint),
# keyed by serial. Seeded by the config flow and replayed via
# discover_devices(cached_credentials=...) so a setup never has to repeat the
# slow, rate-limited Socket.IO password fetch.
CONF_CREDENTIALS: Final = "credentials"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_CONNECT_TIMEOUT: Final = 1.2
DEFAULT_RESPONSE_TIMEOUT: Final = 8.0
