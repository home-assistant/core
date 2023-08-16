"""Support for Honeywell (US) Total Connect Comfort climate systems."""
import logging

DOMAIN = "honeywell"

CONF_COOL_AWAY_TEMPERATURE = "away_cool_temperature"
CONF_HEAT_AWAY_TEMPERATURE = "away_heat_temperature"
DEFAULT_COOL_AWAY_TEMPERATURE = 88
DEFAULT_HEAT_AWAY_TEMPERATURE = 61
CONF_DEV_ID = "thermostat"
CONF_LOC_ID = "location"
<<<<<<< HEAD
TEMPERATURE_STATUS_KEY = "outdoor_temperature"
HUMIDITY_STATUS_KEY = "outdoor_humidity"
=======
OUTDOOR_TEMPERATURE_STATUS_KEY = "outdoor_temperature"
OUTDOOR_HUMIDITY_STATUS_KEY = "outdoor_humidity"
CURRENT_TEMPERATURE_STATUS_KEY = "current_temperature"
CURRENT_HUMIDITY_STATUS_KEY = "current_humidity"
>>>>>>> dde6ce6a996 (Add unit tests)

_LOGGER = logging.getLogger(__name__)
