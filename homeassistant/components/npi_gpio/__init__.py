"""Support for controlling GPIO pins of a Nano Pi."""
import logging

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'npi_gpio'


def setup(hass, config):
    """Set up the Nano PI GPIO component."""
    from NPi import GPIO  # pylint: disable=import-error

    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        GPIO.cleanup()

    def prepare_gpio(event):
        """Stuff to do when home assistant starts."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)
    GPIO.setmode(GPIO.BOARD)
    return True


def setup_output(port):
    """Set up a GPIO as output."""
    from NPi import GPIO  # pylint: disable=import-error
    GPIO.setup(port, GPIO.OUT)


def setup_input(port, pull_mode):
    """Set up a GPIO as input."""
    from NPi import GPIO  # pylint: disable=import-error
    GPIO.setup(port, GPIO.IN,
               GPIO.PUD_DOWN if pull_mode == 'DOWN' else GPIO.PUD_UP)


def write_output(port, value):
    """Write a value to a GPIO."""
    from NPi import GPIO  # pylint: disable=import-error
    GPIO.output(port, value)


def read_input(port):
    """Read a value from a GPIO."""
    from NPi import GPIO  # pylint: disable=import-error
    return GPIO.input(port)


def edge_detect(port, event_callback, bounce):
    """Add detection for RISING and FALLING events."""
    from NPi import GPIO  # pylint: disable=import-error
    GPIO.add_event_detect(port,
                          GPIO.BOTH,
                          callback=event_callback,
                          bouncetime=bounce)
