"""Constants for the rtl_433 integration."""

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "rtl_433"

LOGGER: Final[logging.Logger] = logging.getLogger(__package__)

# Config entries are created at 2.7 rather than 1.1 because the custom component
# of the same domain already ships that schema. Home Assistant refuses to load an
# entry whose version is newer than the flow's, so starting at 1.1 would lock out
# every entry created by that build. ``async_migrate_entry`` covers the older
# schemas it may still hand over.
VERSION: Final = 2
MINOR_VERSION: Final = 7

PLATFORMS: Final[list[Platform]] = [Platform.SENSOR]

MANUFACTURER: Final = "rtl_433"

# Whether to dial the server over ``wss://`` instead of ``ws://``.
CONF_SECURE: Final = "secure"

# ``entry.data[CONF_DEVICES]`` maps ``device_key`` -> a record carrying the
# device's model (``CONF_MODEL``) and the sorted list of observed field keys.
# Written as devices and fields are discovered and read back at setup, so
# entities for known devices exist before the device next transmits.
DEVICE_FIELDS: Final = "fields"

# Default rtl_433 HTTP server port and WebSocket path (the "-F http" defaults).
DEFAULT_PORT: Final = 8433
DEFAULT_PATH: Final = "/ws"

# Seconds of silence after which a device's entities read unavailable. RF devices
# signal presence only by transmitting, so a conservative window tolerates slow
# reporters while still detecting genuinely offline devices.
DEFAULT_AVAILABILITY_TIMEOUT: Final = 600
