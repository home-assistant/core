"""
Support for controlling a Raspberry Pi cover.

Instructions for building the controller can be found here
https://github.com/andrewshilliday/garage-door-controller

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.rpi_gpio/
"""
import logging
from time import sleep

import voluptuous as vol

from homeassistant.components.cover import CoverDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.components.rpi_gpio as rpi_gpio
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_COVERS = 'covers'
CONF_RELAY_PIN = 'relay_pin'
CONF_RELAY_TIME = 'relay_time'
CONF_STATE_PIN = 'state_pin'
CONF_STATE_PULL_MODE = 'state_pull_mode'
CONF_STATE_INVERT = 'state_invert'
CONF_RELAY_INVERT = 'relay_invert'

DEFAULT_RELAY_TIME = .2
DEFAULT_STATE_PULL_MODE = 'UP'
DEFAULT_STATE_INVERT = False
DEFAULT_RELAY_INVERT = False
DEPENDENCIES = ['rpi_gpio']

_COVERS_SCHEMA = vol.All(
    cv.ensure_list,
    [
        vol.Schema({
            CONF_NAME: cv.string,
            CONF_RELAY_PIN: cv.positive_int,
            CONF_STATE_PIN: cv.positive_int,
        })
    ]
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): _COVERS_SCHEMA,
    vol.Optional(CONF_STATE_PULL_MODE, default=DEFAULT_STATE_PULL_MODE):
        cv.string,
    vol.Optional(CONF_RELAY_TIME, default=DEFAULT_RELAY_TIME): cv.positive_int,
    vol.Optional(CONF_STATE_INVERT, default=DEFAULT_STATE_INVERT): cv.boolean,
    vol.Optional(CONF_RELAY_INVERT, default=DEFAULT_RELAY_INVERT): cv.boolean,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the RPi cover platform."""
    relay_time = config.get(CONF_RELAY_TIME)
    state_pull_mode = config.get(CONF_STATE_PULL_MODE)
    state_invert = config.get(CONF_STATE_INVERT)
    relay_invert = config.get(CONF_RELAY_INVERT)
    covers = []
    covers_conf = config.get(CONF_COVERS)

    for cover in covers_conf:
        covers.append(RPiGPIOCover(
            cover[CONF_NAME], cover[CONF_RELAY_PIN], cover[CONF_STATE_PIN],
            state_pull_mode, relay_time, state_invert, relay_invert))
    add_devices(covers)


class RPiGPIOCover(CoverDevice):
    """Representation of a Raspberry GPIO cover."""

    def __init__(self, name, relay_pin, state_pin, state_pull_mode,
                 relay_time, state_invert, relay_invert):
        """Initialize the cover."""
        self._name = name
        self._state = False
        self._relay_pin = relay_pin
        self._state_pin = state_pin
        self._state_pull_mode = state_pull_mode
        self._relay_time = relay_time
        self._state_invert = state_invert
        self._relay_invert = relay_invert
        rpi_gpio.setup_output(self._relay_pin)
        rpi_gpio.setup_input(self._state_pin, self._state_pull_mode)
        rpi_gpio.write_output(self._relay_pin, True != self._relay_invert)

    @property
    def unique_id(self):
        """Return the ID of this cover."""
        return '{}.{}'.format(self.__class__, self._name)

    @property
    def name(self):
        """Return the name of the cover if any."""
        return self._name

    def update(self):
        """Update the state of the cover."""
        self._state = rpi_gpio.read_input(self._state_pin)

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return self._state != self._state_invert

    def _trigger(self):
        """Trigger the cover."""
        rpi_gpio.write_output(self._relay_pin, False != self._relay_invert)
        sleep(self._relay_time)
        rpi_gpio.write_output(self._relay_pin, True != self._relay_invert)

    def close_cover(self):
        """Close the cover."""
        if not self.is_closed:
            self._trigger()

    def open_cover(self):
        """Open the cover."""
        if self.is_closed:
            self._trigger()
