"""Constants for Valux Integration."""
from homeassistant.const import Platform

ATTR_VELOCITY = "velocity"
DOMAIN = "velux"
PLATFORMS = [
    Platform.COVER,
    Platform.LIGHT,
    Platform.SCENE,
]
UPPER_COVER = "upper"
LOWER_COVER = "lower"
DUAL_COVER = "dual"
