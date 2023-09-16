"""Support for Honeywell (US) Total Connect Comfort climate systems."""
import logging

DOMAIN = "honeywell"

CONF_COOL_AWAY_TEMPERATURE = "away_cool_temperature"
CONF_HEAT_AWAY_TEMPERATURE = "away_heat_temperature"
DEFAULT_COOL_AWAY_TEMPERATURE = 88
DEFAULT_HEAT_AWAY_TEMPERATURE = 61
CONF_DEV_ID = "thermostat"
CONF_LOC_ID = "location"
_LOGGER = logging.getLogger(__name__)
