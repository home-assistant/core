"""Constants for the Eufy Security integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "eufy_security"

PLATFORMS: Final = [Platform.CAMERA]

SCAN_INTERVAL: Final = timedelta(minutes=5)

ATTRIBUTION: Final = "Data provided by Eufy Security"

CONF_CONFIG_ENTRY_MINOR_VERSION: Final = 1

# WebSocket add-on configuration
DEFAULT_HOST: Final = "127.0.0.1"
DEFAULT_PORT: Final = 3000

# WebSocket message types
MSG_RESULT: Final = "result"
MSG_EVENT: Final = "event"

# WebSocket schema version (compatible with eufy-security-ws)
SCHEMA_VERSION: Final = 27
