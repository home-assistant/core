"""Constants for Orange Pi GPIO."""

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

CONF_INVERT_LOGIC = "invert_logic"
CONF_PIN_MODE = "pin_mode"
CONF_PORTS = "ports"
DEFAULT_INVERT_LOGIC = False
PIN_MODES = ["pc", "zeroplus", "zeroplus2", "deo", "neocore2"]

_SENSORS_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PORT_SCHEMA = {
    vol.Required(CONF_PORTS): _SENSORS_SCHEMA,
    vol.Required(CONF_PIN_MODE): vol.In(PIN_MODES),
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
}
