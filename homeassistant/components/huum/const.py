"""Constants for the huum integration."""

from homeassistant.const import Platform

DOMAIN = "huum"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.SENSOR,
]
UPDATE_INTERVAL = 30
