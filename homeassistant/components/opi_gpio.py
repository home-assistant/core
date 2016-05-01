"""
Support for controlling GPIO pins of a Orange Pi.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/opi_gpio/
"""
# pylint: disable=import-error
import logging

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['git+git://github.com/Toshik/orangepi_PC_gpio_pyH3.git@master#pyA20==0.2.1']
DOMAIN = "opi_gpio"
_LOGGER = logging.getLogger(__name__)


# pylint: disable=no-member
def setup(hass, config):
    """Setup the Orange PI GPIO component."""
    from pyA20.gpio import gpio

    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        #GPIO.cleanup()

    def prepare_gpio(event):
        """Stuff to do when home assistant starts."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)
    gpio.init()
    return True


def setup_output(port):
    """Setup a GPIO as output."""
    from pyA20.gpio import gpio
    gpio.setcfg(port, gpio.OUTPUT)


def setup_input(port, pull_mode):
    """Setup a GPIO as input."""
    from pyA20.gpio import gpio
    gpio.setcfg(port, gpio.INPUT)
    gpio.pullup(port, gpio.PULLDOWN if pull_mode == 'DOWN' else gpio.PULLUP)


def write_output(port, value):
    """Write a value to a GPIO."""
    from pyA20.gpio import gpio
    gpio.output(port, value)


def read_input(port):
    """Read a value from a GPIO."""
    from pyA20.gpio import gpio
    return gpio.input(port)


def edge_detect(port, event_callback, bounce):
    """Add detection for RISING and FALLING events."""
#    import RPi.GPIO as GPIO
#    GPIO.add_event_detect(
#        port,
#        GPIO.BOTH,
#        callback=event_callback,
#        bouncetime=bounce)
