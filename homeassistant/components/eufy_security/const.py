"""Constants for the Eufy Security integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "eufy_security"

PLATFORMS: Final = [Platform.CAMERA]

SCAN_INTERVAL: Final = timedelta(minutes=5)

ATTRIBUTION: Final = "Data provided by Eufy Security"

CONF_CONFIG_ENTRY_MINOR_VERSION: Final = 2

# Session state (opaque dict managed by the library)
CONF_SESSION_STATE: Final = "session_state"

# RTSP streaming credentials (configured via options flow)
CONF_RTSP_CREDENTIALS: Final = "rtsp_credentials"
CONF_RTSP_USERNAME: Final = "rtsp_username"
CONF_RTSP_PASSWORD: Final = "rtsp_password"

# State attributes
ATTR_SERIAL_NUMBER: Final = "serial_number"
ATTR_STATION_SERIAL: Final = "station_serial"
ATTR_HARDWARE_VERSION: Final = "hardware_version"
ATTR_SOFTWARE_VERSION: Final = "software_version"
ATTR_IP_ADDRESS: Final = "ip_address"
