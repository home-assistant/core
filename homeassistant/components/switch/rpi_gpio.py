"""
homeassistant.components.switch.rpi_gpio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to control the GPIO pins of a Raspberry Pi.

Note: To use RPi GPIO, Home Assistant must be run as root.

Configuration:

To use the Raspberry GPIO switches you will need to add something like the
following to your configuration.yaml file.

switch:
  platform: rpi_gpio
  invert_logic: false
  ports:
    11: Fan Office
    12: Light Desk

Variables:

invert_logic
*Optional
If true, inverts the output logic to ACTIVE LOW. Default is false (ACTIVE HIGH)

ports
*Required
An array specifying the GPIO ports to use and the name to use in the frontend.
"""

import logging
try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (DEVICE_DEFAULT_NAME,
                                 EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP)

DEFAULT_INVERT_LOGIC = False

REQUIREMENTS = ['RPi.GPIO==0.5.11']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Raspberry PI GPIO ports. """
    if GPIO is None:
        _LOGGER.error('RPi.GPIO not available. rpi_gpio ports ignored.')
        return
    # pylint: disable=no-member
    GPIO.setmode(GPIO.BCM)

    switches = []
    invert_logic = config.get('invert_logic', DEFAULT_INVERT_LOGIC)
    ports = config.get('ports')
    for port_num, port_name in ports.items():
        switches.append(RPiGPIOSwitch(port_name, port_num, invert_logic))
    add_devices(switches)

    def cleanup_gpio(event):
        """ Stuff to do before stop home assistant. """
        # pylint: disable=no-member
        GPIO.cleanup()

    def prepare_gpio(event):
        """ Stuff to do when home assistant starts. """
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)


class RPiGPIOSwitch(ToggleEntity):
    """ Represents a port that can be toggled using Raspberry Pi GPIO. """

    def __init__(self, name, gpio, invert_logic):
        self._name = name or DEVICE_DEFAULT_NAME
        self._gpio = gpio
        self._active_state = not invert_logic
        self._state = not self._active_state
        # pylint: disable=no-member
        GPIO.setup(gpio, GPIO.OUT)

    @property
    def name(self):
        """ The name of the port. """
        return self._name

    @property
    def should_poll(self):
        """ No polling needed. """
        return False

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        if self._switch(self._active_state):
            self._state = True
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        if self._switch(not self._active_state):
            self._state = False
        self.update_ha_state()

    def _switch(self, new_state):
        """ Change the output value to Raspberry Pi GPIO port. """
        _LOGGER.info('Setting GPIO %s to %s', self._gpio, new_state)
        # pylint: disable=bare-except
        try:
            # pylint: disable=no-member
            GPIO.output(self._gpio, 1 if new_state else 0)
        except:
            _LOGGER.error('GPIO "%s" output failed', self._gpio)
            return False
        return True

    # pylint: disable=no-self-use
    @property
    def device_state_attributes(self):
        """ Returns device specific state attributes. """
        return None

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        data = {}
        device_attr = self.device_state_attributes
        if device_attr is not None:
            data.update(device_attr)
        return data
