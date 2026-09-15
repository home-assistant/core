"""Constants for the rtl_433 integration."""

import logging
from typing import Final

from homeassistant.const import Platform

# Integration domain. Must match the "domain" key in manifest.json.
DOMAIN: Final = "rtl_433"

# Module-level logger shared across the package.
LOGGER: Final[logging.Logger] = logging.getLogger(__package__)

# Config-entry schema version. Kept identical to the full HACS build so an entry
# created (or migrated up to) version 2 / minor 7 by that build loads in this
# build without a downgrade. See ``COMPATIBILITY_CONTRACT.md`` section 1.
VERSION: Final = 2
MINOR_VERSION: Final = 7

# The only platform this minimal build forwards.
PLATFORMS: Final[list[Platform]] = [Platform.SENSOR]

# Generic device-registry manufacturer for the hub and its nested RF devices.
MANUFACTURER: Final = "rtl_433"

# --- Hub connection config-entry keys --------------------------------------
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_PATH: Final = "path"
# Whether to dial the server over ``wss://`` instead of ``ws://``.
CONF_SECURE: Final = "secure"

# --- Hub devices-map keys (read from migrated entries) ----------------------
# ``entry.data[CONF_DEVICES]`` maps ``device_key`` -> a record carrying the
# device's model and the sorted list of observed field keys. The full build
# writes this map; this build reads it at setup so entities for already-adopted
# devices are recreated on startup (they survive a restart even before the
# device next transmits).
CONF_DEVICES: Final = "devices"
CONF_MODEL: Final = "model"
DEVICE_FIELDS: Final = "fields"

# --- Defaults ---------------------------------------------------------------
# Default rtl_433 HTTP server port (the documented "-F http" default).
DEFAULT_PORT: Final = 8433
# Default WebSocket path on the rtl_433 HTTP server.
DEFAULT_PATH: Final = "/ws"
# Seconds of silence after which a device's entities read unavailable. RF
# devices signal presence only by transmitting, so a conservative window
# tolerates slow reporters while still detecting genuinely offline devices.
DEFAULT_AVAILABILITY_TIMEOUT: Final = 600
