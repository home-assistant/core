"""
homeassistant.components.rpi_gpio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to control the GPIO pins of a Raspberry Pi.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rpi_gpio/
"""

import logging
try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None
from homeassistant.const import (EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP)
REQUIREMENTS = ['RPi.GPIO==0.6.1']
DOMAIN = "rpi_gpio"
_LOGGER = logging.getLogger(__name__)


# pylint: disable=no-member
def setup(hass, config):
    """ Sets up the Raspberry PI GPIO component. """
    if GPIO is None:
        _LOGGER.error('RPi.GPIO not available. rpi_gpio ports ignored.')
        return False

    def cleanup_gpio(event):
        """ Stuff to do before stop home assistant. """
        GPIO.cleanup()

    def prepare_gpio(event):
        """ Stuff to do when home assistant starts. """
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)
    GPIO.setmode(GPIO.BCM)
    return True


def setup_output(port):
    """ Setup a GPIO as output. """
    GPIO.setup(port, GPIO.OUT)


def setup_input(port, pull_mode):
    """ Setup a GPIO as input. """
    GPIO.setup(port, GPIO.IN,
               GPIO.PUD_DOWN if pull_mode == 'DOWN' else GPIO.PUD_UP)


def write_output(port, value):
    """ Write a value to a GPIO. """
    GPIO.output(port, value)


def read_input(port):
    """ Read a value from a GPIO. """
    return GPIO.input(port)


def edge_detect(port, event_callback, bounce):
    """ Adds detection for RISING and FALLING events. """
    GPIO.add_event_detect(
        port,
        GPIO.BOTH,
        callback=event_callback,
        bouncetime=bounce)
