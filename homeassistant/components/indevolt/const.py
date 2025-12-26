"""Constants for the indevolt integration."""

from homeassistant.const import Platform

DOMAIN = "indevolt"
DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = 30
PLATFORMS = [Platform.SENSOR]

SUPPORTED_MODELS = ["BK1600/BK1600Ultra", "SolidFlex/PowerFlex2000"]
