"""Constants for IPMA component."""
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

DOMAIN = "ipma"

HOME_LOCATION_NAME = "Home"

ATTRIBUTION = "Instituto Português do Mar e Atmosfera"

ENTITY_ID_SENSOR_FORMAT_HOME = f"{WEATHER_DOMAIN}.ipma_{HOME_LOCATION_NAME}"

FORECAST_MODE = ["hourly", "daily"]

IPMA_API = "ipma_api"
IPMA_LOCATION = "ipma_location"

FORECAST_PERIOD = "Para o periodo:"
MIN_WAVE_HIGH = "min altura das ondas (m)"
MAX_WAVE_HIGH = "max altura das ondas (m)"
MIN_TEMPERATURE = "min temperatura mar (C)"
MAX_TEMPERATURE = "max temperatura mar (C)"
MIN_SWELL_PERIOD = "min periodo de pico (swell) (s)"
MAX_SWELL_PERIOD = "max periodo de pico (swell) (s)"
MIN_SWELL_HIGH = "min altura (swell) (m)"
MAX_SWELL_HIGH = "max altura (swell) (m)"
WAVE_DIRECTION = "rumo predominante das ondas"
