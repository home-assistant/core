"""Support for controlling GPIO pins of a Raspberry Pi."""
import logging

from gpiozero import LED, Button
from gpiozero.pins.pigpio import PiGPIOFactory

_LOGGER = logging.getLogger(__name__)

CONF_BOUNCETIME = "bouncetime"
CONF_INVERT_LOGIC = "invert_logic"
CONF_PULL_MODE = "pull_mode"

DEFAULT_BOUNCETIME = 50
DEFAULT_INVERT_LOGIC = False
DEFAULT_PULL_MODE = "UP"

DOMAIN = "remote_rpi_gpio"


def setup(hass, config):
    """Set up the Raspberry Pi Remote GPIO component."""
    return True


def setup_output(address, port, invert_logic):
    """Set up a GPIO as output."""

    try:
        return LED(
            port, active_high=not invert_logic, pin_factory=PiGPIOFactory(address)
        )
    except (ValueError, IndexError, KeyError):
        return None


def setup_input(address, port, pull_mode, bouncetime):
    """Set up a GPIO as input."""

    if pull_mode == "UP":
        pull_gpio_up = True
    elif pull_mode == "DOWN":
        pull_gpio_up = False

    try:
        return Button(
            port,
            pull_up=pull_gpio_up,
            bounce_time=bouncetime,
            pin_factory=PiGPIOFactory(address),
        )
    except (ValueError, IndexError, KeyError, OSError):
        return None


def write_output(switch, value):
    """Write a value to a GPIO."""
    if value == 1:
        switch.on()
    if value == 0:
        switch.off()


def read_input(button):
    """Read a value from a GPIO."""
    return button.is_pressed
