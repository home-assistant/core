"""Constants for the Homewizard integration."""
from __future__ import annotations

from typing import Final

# Set up.
from homeassistant.const import Platform

DOMAIN = "homewizard"
MANUFACTURER = "HomeWizard"
PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

# Platform config.
CONF_SERIAL: Final = "serial"
CONF_PRODUCT_NAME: Final = "product_name"
CONF_PRODUCT_TYPE: Final = "product_type"
CONF_DEVICE: Final = "device"
CONF_DATA: Final = "data"

# Services
SERVICE_DEVICE: Final = "device"
SERVICE_DATA: Final = "data"
SERVICE_STATE: Final = "state"
