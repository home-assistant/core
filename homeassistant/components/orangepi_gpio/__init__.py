"""Support for controlling GPIO pins of a Orange Pi."""
import logging

from OPi import GPIO
import nanopi.duo
import nanopi.neocore2
import orangepi.pc
import orangepi.zeroplus

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP

_LOGGER = logging.getLogger(__name__)

CONF_PIN_MODE = "pin_mode"
DOMAIN = "orangepi_gpio"
PIN_MODES = ["pc", "zeroplus", "zeroplus2", "deo", "neocore2"]


def setup(hass, config):
    """Set up the Orange Pi GPIO component."""

    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        GPIO.cleanup()

    def prepare_gpio(event):
        """Stuff to do when home assistant starts."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)
    return True


def setup_mode(mode):
    """Set GPIO pin mode."""

    if mode == "pc":

        GPIO.setmode(orangepi.pc.BOARD)
    elif mode == "zeroplus":

        GPIO.setmode(orangepi.zeroplus.BOARD)
    elif mode == "zeroplus2":

        GPIO.setmode(orangepi.zeroplus2.BOARD)
    elif mode == "duo":

        GPIO.setmode(nanopi.duo.BOARD)
    elif mode == "neocore2":

        GPIO.setmode(nanopi.neocore2.BOARD)


def setup_output(port):
    """Set up a GPIO as output."""

    GPIO.setup(port, GPIO.OUT)


def setup_input(port):
    """Set up a GPIO as input."""

    GPIO.setup(port, GPIO.IN)


def write_output(port, value):
    """Write a value to a GPIO."""

    GPIO.output(port, value)


def read_input(port):
    """Read a value from a GPIO."""

    return GPIO.input(port)


def edge_detect(port, event_callback):
    """Add detection for RISING and FALLING events."""

    GPIO.add_event_detect(port, GPIO.BOTH, callback=event_callback)
