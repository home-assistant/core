"""Constants for Valux Integration."""
from homeassistant.const import Platform

ATTR_VELOCITY = "velocity"
DOMAIN = "velux"
PLATFORMS = [
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.SWITCH,
]
UPPER_COVER = "upper"
LOWER_COVER = "lower"
DUAL_COVER = "dual"
