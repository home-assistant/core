"""Define constants for OpenAQ integration."""

from homeassistant.const import Platform

DOMAIN = "openAQ"
SENSOR_ID = "sensorid"
DEFAULT_SENSOR_ID = "1234"

SENSOR = "sensor"

ICON = "mdi:air-filter"

PLATFORMS = [
    Platform.SENSOR,
]
