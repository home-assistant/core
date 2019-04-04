"""Support for controlling GPIO pins of a Beaglebone Black."""
import logging

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['Adafruit_BBIO==1.0.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'bbb_gpio'


def setup(hass, config):
    """Set up the BeagleBone Black GPIO component."""
    # pylint: disable=import-error
    from Adafruit_BBIO import GPIO

    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        GPIO.cleanup()

    def prepare_gpio(event):
        """Stuff to do when home assistant starts."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)
    return True


def setup_output(pin):
    """Set up a GPIO as output."""
    # pylint: disable=import-error
    from Adafruit_BBIO import GPIO
    GPIO.setup(pin, GPIO.OUT)


def setup_input(pin, pull_mode):
    """Set up a GPIO as input."""
    # pylint: disable=import-error
    from Adafruit_BBIO import GPIO
    GPIO.setup(pin, GPIO.IN,
               GPIO.PUD_DOWN if pull_mode == 'DOWN'
               else GPIO.PUD_UP)


def write_output(pin, value):
    """Write a value to a GPIO."""
    # pylint: disable=import-error
    from Adafruit_BBIO import GPIO
    GPIO.output(pin, value)


def read_input(pin):
    """Read a value from a GPIO."""
    # pylint: disable=import-error
    from Adafruit_BBIO import GPIO
    return GPIO.input(pin) is GPIO.HIGH


def edge_detect(pin, event_callback, bounce):
    """Add detection for RISING and FALLING events."""
    # pylint: disable=import-error
    from Adafruit_BBIO import GPIO
    GPIO.add_event_detect(
        pin, GPIO.BOTH, callback=event_callback, bouncetime=bounce)
