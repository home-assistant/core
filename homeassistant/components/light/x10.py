"""
Support for X10 lights.

Requires heyu x10 interface
http://www.heyu.org

To enable x10 lights, add something like this to your `configuration.yaml`:

    light:
    - platform: x10
        lights:
        - name: Living Room Lamp
            id: a2
        - name: Bedroom Lamp
            id: a3

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.x10/
"""

import logging
from subprocess import check_output, CalledProcessError, STDOUT
from homeassistant.components.light import ATTR_BRIGHTNESS, Light

_LOGGER = logging.getLogger(__name__)


def x10_command(command):
    """Execute X10 command and check output."""
    return check_output(["heyu"] + command.split(' '), stderr=STDOUT)


def get_status():
    """Get on/off status for all x10 units in default housecode."""
    output = check_output("heyu info | grep monitored", shell=True)
    return output.decode('utf-8').split(' ')[-1].strip('\n()')


def get_unit_status(code):
    """Get on/off status for given unit."""
    unit = int(code[1])
    return get_status()[16 - int(unit)] == '1'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Initialize Awesome Light platform."""
    # Verify that heyu is active
    try:
        x10_command("info")
    except CalledProcessError as err:
        _LOGGER.error(err.output)
        return False

    # Add devices
    add_devices(X10Light(light) for light in config['lights'])


class X10Light(Light):
    """Represents an X10 Light in Home Assistant."""

    def __init__(self, light):
        """Initialize an X10 Light."""
        self._name = light['name']
        self._id = light['id']
        self._is_on = False
        self._brightness = 0

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Brightness of the light (an integer in the range 1-255).

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def is_on(self):
        """If light is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        x10_command("on " + self._id)
        self._brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._is_on = True

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        x10_command("off " + self._id)
        self._is_on = False

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assitant.
        """
        self._is_on = get_unit_status(self._id)
