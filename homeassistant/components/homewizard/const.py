"""Constants for the Homewizard integration."""
from __future__ import annotations

from typing import Final

# Set up.
from homeassistant.const import Platform

DOMAIN = "homewizard"
MANUFACTURER = "HomeWizard"
PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

# Platform config.
CONF_API_ENABLED: Final = "api_enabled"
CONF_DATA: Final = "data"
CONF_DEVICE: Final = "device"
CONF_PATH: Final = "path"
CONF_PRODUCT_NAME: Final = "product_name"
CONF_PRODUCT_TYPE: Final = "product_type"
CONF_SERIAL: Final = "serial"


# Services
SERVICE_DEVICE: Final = "device"
SERVICE_DATA: Final = "data"
SERVICE_STATE: Final = "state"
