"""Support for controlling a Nano Pi cover."""
import logging
from time import sleep

import voluptuous as vol

from homeassistant.components.cover import CoverDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.components import npi_gpio
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_COVERS = 'covers'
CONF_RELAY_PORT = 'relay_port'
CONF_RELAY_TIME = 'relay_time'
CONF_STATE_PORT = 'state_port'
CONF_STATE_PULL_MODE = 'state_pull_mode'
CONF_INITIAL = 'initial'
CONF_INVERT_STATE = 'invert_state'
CONF_INVERT_RELAY = 'invert_relay'

DEFAULT_INITIAL = False
DEFAULT_RELAY_TIME = .2
DEFAULT_STATE_PULL_MODE = 'UP'
DEFAULT_INVERT_STATE = False
DEFAULT_INVERT_RELAY = False


_COVERS_SCHEMA = vol.All(cv.ensure_list,
                         [vol.Schema({
                             CONF_NAME: cv.string,
                             CONF_RELAY_PORT: cv.positive_int,
                             CONF_STATE_PORT: cv.positive_int,
                         })])

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): _COVERS_SCHEMA,
    vol.Optional(CONF_STATE_PULL_MODE, default=DEFAULT_STATE_PULL_MODE):
        cv.string,
    vol.Optional(CONF_RELAY_TIME, default=DEFAULT_RELAY_TIME): cv.positive_int,
    vol.Optional(CONF_INITIAL, default=DEFAULT_INITIAL): cv.boolean,
    vol.Optional(CONF_INVERT_STATE, default=DEFAULT_INVERT_STATE): cv.boolean,
    vol.Optional(CONF_INVERT_RELAY, default=DEFAULT_INVERT_RELAY): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NPi cover platform."""
    initial = config.get(CONF_INITIAL)
    relay_time = config.get(CONF_RELAY_TIME)
    state_pull_mode = config.get(CONF_STATE_PULL_MODE)
    invert_state = config.get(CONF_INVERT_STATE)
    invert_relay = config.get(CONF_INVERT_RELAY)
    covers = []
    covers_conf = config.get(CONF_COVERS)

    for cover in covers_conf:
        covers.append(NPiGPIOCover(cover[CONF_NAME], cover[CONF_RELAY_PORT],
                                   cover[CONF_STATE_PORT], state_pull_mode,
                                   relay_time, initial, invert_state,
                                   invert_relay))
    add_entities(covers)


class NPiGPIOCover(CoverDevice):
    """Representation of a Nano Pi GPIO cover."""

    def __init__(self, name, relay_port, state_port, state_pull_mode,
                 relay_time, initial, invert_state, invert_relay):
        """Initialize the cover."""
        self._name = name
        self._state = initial
        self._relay_port = relay_port
        self._state_port = state_port
        self._state_pull_mode = state_pull_mode
        self._relay_time = relay_time
        self._invert_state = invert_state
        self._invert_relay = invert_relay
        npi_gpio.setup_output(self._relay_port)
        npi_gpio.setup_input(self._state_port, self._state_pull_mode)
        npi_gpio.write_output(self._relay_port, 0 if self._invert_relay else 1)

    @property
    def name(self):
        """Return the name of the cover if any."""
        return self._name

    def update(self):
        """Update the state of the cover."""
        self._state = npi_gpio.read_input(self._state_port)

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return self._state != self._invert_state

    def _trigger(self):
        """Trigger the cover."""
        npi_gpio.write_output(self._relay_port, 1 if self._invert_relay else 0)
        sleep(self._relay_time)
        npi_gpio.write_output(self._relay_port, 0 if self._invert_relay else 1)

    def close_cover(self, **kwargs):
        """Close the cover."""
        if not self.is_closed:
            self._trigger()

    def open_cover(self, **kwargs):
        """Open the cover."""
        if self.is_closed:
            self._trigger()
