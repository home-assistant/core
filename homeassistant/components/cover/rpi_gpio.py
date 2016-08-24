"""
Support for building a Raspberry Pi cover in HA.

Instructions for building the controller can be found here
https://github.com/andrewshilliday/garage-door-controller

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.rpi_gpio/
"""

import logging
from time import sleep
import voluptuous as vol

from homeassistant.components.cover import CoverDevice
import homeassistant.components.rpi_gpio as rpi_gpio
import homeassistant.helpers.config_validation as cv

RELAY_TIME = 'relay_time'
STATE_PULL_MODE = 'state_pull_mode'
DEFAULT_PULL_MODE = 'UP'
DEFAULT_RELAY_TIME = .2
DEPENDENCIES = ['rpi_gpio']

_LOGGER = logging.getLogger(__name__)

_COVERS_SCHEMA = vol.All(
    cv.ensure_list,
    [
        vol.Schema({
            'name': str,
            'relay_pin': int,
            'state_pin': int,
        })
    ]
)
PLATFORM_SCHEMA = vol.Schema({
    'platform': str,
    vol.Required('covers'): _COVERS_SCHEMA,
    vol.Optional(STATE_PULL_MODE, default=DEFAULT_PULL_MODE): cv.string,
    vol.Optional(RELAY_TIME, default=DEFAULT_RELAY_TIME): vol.Coerce(int),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the cover platform."""
    relay_time = config.get(RELAY_TIME)
    state_pull_mode = config.get(STATE_PULL_MODE)
    covers = []
    covers_conf = config.get('covers')

    for cover in covers_conf:
        covers.append(RPiGPIOCover(cover['name'], cover['relay_pin'],
                                   cover['state_pin'],
                                   state_pull_mode,
                                   relay_time))
    add_devices(covers)


# pylint: disable=abstract-method
class RPiGPIOCover(CoverDevice):
    """Representation of a Raspberry cover."""

    # pylint: disable=too-many-arguments
    def __init__(self, name, relay_pin, state_pin,
                 state_pull_mode, relay_time):
        """Initialize the cover."""
        self._name = name
        self._state = False
        self._relay_pin = relay_pin
        self._state_pin = state_pin
        self._state_pull_mode = state_pull_mode
        self._relay_time = relay_time
        rpi_gpio.setup_output(self._relay_pin)
        rpi_gpio.setup_input(self._state_pin, self._state_pull_mode)
        rpi_gpio.write_output(self._relay_pin, True)

    @property
    def unique_id(self):
        """Return the ID of this cover."""
        return "{}.{}".format(self.__class__, self._name)

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
        return self._state

    def _trigger(self):
        """Trigger the cover."""
        rpi_gpio.write_output(self._relay_pin, False)
        sleep(self._relay_time)
        rpi_gpio.write_output(self._relay_pin, True)

    def close_cover(self):
        """Close the cover."""
        if not self.is_closed:
            self._trigger()

    def open_cover(self):
        """Open the cover."""
        if self.is_closed:
            self._trigger()
