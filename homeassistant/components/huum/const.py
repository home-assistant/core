"""Constants for the huum integration."""

from homeassistant.const import Platform

DOMAIN = "huum"

PLATFORMS = [
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]
UPDATE_INTERVAL = 30
