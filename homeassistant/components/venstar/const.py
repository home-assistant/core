"""The venstar component."""
import logging

DOMAIN = "venstar"

ATTR_FAN_STATE = "fan_state"
ATTR_HVAC_STATE = "hvac_mode"

CONF_HUMIDIFIER = "humidifier"

DEFAULT_SSL = False

HOLD_MODE_OFF = "off"
HOLD_MODE_TEMPERATURE = "temperature"

VENSTAR_TIMEOUT = 5
VENSTAR_SLEEP = 1.0

_LOGGER = logging.getLogger(__name__)
