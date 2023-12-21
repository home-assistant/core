"""Constants for Valux Integration."""
from homeassistant.const import Platform

DOMAIN = "velux"
PLATFORMS = [
    Platform.COVER,
    Platform.LIGHT,
    Platform.SCENE,
]
