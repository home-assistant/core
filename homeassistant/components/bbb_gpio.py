"""
Support for controlling GPIO pins of a Beaglebone Black.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/bbb_gpio/
"""
import logging

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['Adafruit_BBIO==1.0.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'bbb_gpio'


# pylint: disable=no-member
def setup(hass, config):
    """Setup the Beaglebone black GPIO component."""
    import Adafruit_BBIO.GPIO as GPIO

    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        GPIO.cleanup()

    def prepare_gpio(event):
        """Stuff to do when home assistant starts."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)
    return True


def setup_output(port):
    """Setup a GPIO as output."""
    import Adafruit_BBIO.GPIO as GPIO
    GPIO.setup(port, GPIO.OUT)


def setup_input(port, pull_mode):
    """Setup a GPIO as input."""
    import Adafruit_BBIO.GPIO as GPIO
    GPIO.setup(port, GPIO.IN,
               GPIO.PUD_DOWN if pull_mode == 'DOWN' else GPIO.PUD_UP)


def write_output(port, value):
    """Write a value to a GPIO."""
    import Adafruit_BBIO.GPIO as GPIO
    GPIO.output(port, value)


def read_input(port):
    """Read a value from a GPIO."""
    import Adafruit_BBIO.GPIO as GPIO
    return GPIO.input(port)


def edge_detect(port, event_callback, bounce):
    """Add detection for RISING and FALLING events."""
    import Adafruit_BBIO.GPIO as GPIO
    GPIO.add_event_detect(
        port,
        GPIO.BOTH,
        callback=event_callback,
        bouncetime=bounce)
