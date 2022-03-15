"""The venstar component."""
import logging

from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)
from homeassistant.const import STATE_ON

DOMAIN = "venstar"

ATTR_FAN_STATE = "fan_state"
ATTR_HVAC_STATE = "hvac_mode"

CONF_HUMIDIFIER = "humidifier"

DEFAULT_SSL = False

VALID_FAN_STATES = [STATE_ON, HVAC_MODE_AUTO]
VALID_THERMOSTAT_MODES = [HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF, HVAC_MODE_AUTO]

HOLD_MODE_OFF = "off"
HOLD_MODE_TEMPERATURE = "temperature"

VENSTAR_TIMEOUT = 5
VENSTAR_SLEEP = 1.0

_LOGGER = logging.getLogger(__name__)
