"""Constants for the BSB-Lan integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

# Integration domain
DOMAIN: Final = "bsblan"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=12)  # Legacy interval, kept for compatibility
SCAN_INTERVAL_FAST = timedelta(seconds=12)  # For state/sensor data
SCAN_INTERVAL_SLOW = timedelta(minutes=5)  # For config data

# Services
DATA_BSBLAN_CLIENT: Final = "bsblan_client"

ATTR_TARGET_TEMPERATURE: Final = "target_temperature"
ATTR_INSIDE_TEMPERATURE: Final = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE: Final = "outside_temperature"

CONF_PASSKEY: Final = "passkey"

DEFAULT_PORT: Final = 80
