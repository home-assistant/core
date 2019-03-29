"""Constants for Orange Pi GPIO."""
import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from . import CONF_PINMODE, PINMODES

CONF_INVERT_LOGIC = 'invert_logic'
CONF_PORTS = 'ports'

DEFAULT_INVERT_LOGIC = False

_SENSORS_SCHEMA = vol.Schema({
    cv.positive_int: cv.string,
})

PORT_SCHEMA = {
    vol.Required(CONF_PORTS): _SENSORS_SCHEMA,
    vol.Required(CONF_PINMODE): vol.In(PINMODES),
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
}
