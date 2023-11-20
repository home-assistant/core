"""Define constants for OpenAQ integration."""

from homeassistant.const import Platform

DOMAIN = "openAQ"
SENSOR_ID = "sensorid"
DEFAULT_SENSOR_ID = "1234"

API_KEY_ID = "apiid"
CITY_ID = "cityid"
LOCATION_ID = "locationid"

SENSOR = "sensor"

ICON = "mdi:air-filter"

PLATFORMS = [
    Platform.SENSOR,
]
