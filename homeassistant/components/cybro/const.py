"""Constants for the Cybro PLC integration."""
from datetime import timedelta
import logging
from typing import Final

# Integration domain
DOMAIN = "cybro"

MANUFACTURER = "Cybrotech Ltd"
MANUFACTURER_URL = "https://www.cybrotech.com"
ATTRIBUTION_PLC = "Data read from Cybro 2/3 PLC"
DEVICE_DESCRIPTION = "Cybro 2/3 PLC"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)

# Options

# Attributes
AREA_SYSTEM = "System"
AREA_ENERGY = "Energy"
AREA_WEATHER = "Weather"
AREA_LIGHTS = "Lights"

# Device classes
DEVICE_CLASS_CYBRO_LIVE_OVERRIDE: Final = "cybro__live_override"
