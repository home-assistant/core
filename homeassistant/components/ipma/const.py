"""Constants for IPMA component."""
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

DOMAIN = "ipma"

HOME_LOCATION_NAME = "Home"

DATA_API = "api"
DATA_LOCATION = "location"

ENTITY_ID_SENSOR_FORMAT_HOME = f"{WEATHER_DOMAIN}.ipma_{HOME_LOCATION_NAME}"
