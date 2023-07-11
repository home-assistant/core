"""Constants for the BSB-Lan integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

# Integration domain
DOMAIN: Final = "bsblan"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=12)

# Services
DATA_BSBLAN_CLIENT: Final = "bsblan_client"

ATTR_TARGET_TEMPERATURE: Final = "target_temperature"
ATTR_INSIDE_TEMPERATURE: Final = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE: Final = "outside_temperature"

CONF_PASSKEY: Final = "passkey"

CONF_DEVICE_IDENT: Final = "RVS21.831F/127"

DEFAULT_PORT: Final = 80
