"""
homeassistant.components.switch.arduino
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Support for switching Arduino pins on and off.

switch:
  platform: arduino
  pins:
    11:
      name: Fan Office
    12:
      name: Light Desk

VARIABLES:

pins
*Required
An array specifying the digital pins to use on the Arduino board.

These are the variables for the pins array:

name
*Required
The name for the pin that will be used in the frontend.

"""
import logging

from homeassistant.components.arduino import (BOARD, ArduinoDeviceABC)
from homeassistant.const import STATE_ON, STATE_OFF

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Arduino platform. """

    # Verify that Arduino board is present
    # if BOARD is None:
    #     _LOGGER.error('A connection has not been made to the Arduino board.')
    #
    #     return False

    switches = []
    pins = config.get('pins')
    for pinnum, pin in pins.items():
        if pin.get('name'):
            switches.append(ArduinoSwitchDevice(pin.get('name'), pinnum))
    add_devices(switches)


class ArduinoSwitchDevice(ArduinoDeviceABC):
    """ Represents an Arduino switch within Home Assistant. """

    _domain = 'switch'
    _dtype = 'digital'
    _states = [STATE_ON, STATE_OFF]
