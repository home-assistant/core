"""Support for controlling GPIO pins of a Orange Pi."""
import logging

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

_LOGGER = logging.getLogger(__name__)

CONF_PIN_MODE = 'pin_mode'
DOMAIN = 'orangepi_gpio'
PIN_MODES = ['pc', 'zeroplus', 'zeroplus2', 'deo', 'neocore2']


def setup(hass, config):
    """Set up the Orange Pi GPIO component."""
    from OPi import GPIO

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
    from OPi import GPIO

    if mode == 'pc':
        import orangepi.pc
        GPIO.setmode(orangepi.pc.BOARD)
    elif mode == 'zeroplus':
        import orangepi.zeroplus
        GPIO.setmode(orangepi.zeroplus.BOARD)
    elif mode == 'zeroplus2':
        import orangepi.zeroplus
        GPIO.setmode(orangepi.zeroplus2.BOARD)
    elif mode == 'duo':
        import nanopi.duo
        GPIO.setmode(nanopi.duo.BOARD)
    elif mode == 'neocore2':
        import nanopi.neocore2
        GPIO.setmode(nanopi.neocore2.BOARD)


def setup_output(port):
    """Set up a GPIO as output."""
    from OPi import GPIO
    GPIO.setup(port, GPIO.OUT)


def setup_input(port):
    """Set up a GPIO as input."""
    from OPi import GPIO
    GPIO.setup(port, GPIO.IN)


def write_output(port, value):
    """Write a value to a GPIO."""
    from OPi import GPIO
    GPIO.output(port, value)


def read_input(port):
    """Read a value from a GPIO."""
    from OPi import GPIO
    return GPIO.input(port)


def edge_detect(port, event_callback):
    """Add detection for RISING and FALLING events."""
    from OPi import GPIO
    GPIO.add_event_detect(
        port,
        GPIO.BOTH,
        callback=event_callback)
