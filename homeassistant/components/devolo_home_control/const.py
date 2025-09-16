"""Constants for the devolo_home_control integration."""

from homeassistant.const import Platform

DOMAIN = "devolo_home_control"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
]
SUPPORTED_MODEL_TYPES = ["2600", "2601"]
