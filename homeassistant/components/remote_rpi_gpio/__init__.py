"""Support for controlling GPIO pins of a Raspberry Pi."""
from gpiozero import LED, DigitalInputDevice
from gpiozero.pins.pigpio import PiGPIOFactory
import voluptuous as vol

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

CONF_BOUNCETIME = "bouncetime"
CONF_INVERT_LOGIC = "invert_logic"
CONF_PULL_MODE = "pull_mode"
CONF_PINS = "pins"

PINS_SCHEMA = vol.Schema({cv.positive_int: cv.string})

DEFAULT_BOUNCETIME = 50
DEFAULT_INVERT_LOGIC = False
DEFAULT_PULL_MODE = "UP"
DEFAULT_PORT = 8888

DOMAIN = "remote_rpi_gpio"


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Raspberry Pi Remote GPIO component."""
    return True


def setup_output(address, port, pin, invert_logic):
    """Set up a GPIO as output."""

    try:
        return LED(
            pin, active_high=not invert_logic, pin_factory=PiGPIOFactory(address, port)
        )
    except (ValueError, IndexError, KeyError):
        return None


def setup_input(address, port, pin, pull_mode, bouncetime):
    """Set up a GPIO as input."""

    if pull_mode == "UP":
        pull_gpio_up = True
    elif pull_mode == "DOWN":
        pull_gpio_up = False

    try:
        return DigitalInputDevice(
            pin,
            pull_up=pull_gpio_up,
            bounce_time=bouncetime,
            pin_factory=PiGPIOFactory(address, port),
        )
    except (ValueError, IndexError, KeyError, OSError):
        return None


def write_output(switch, value):
    """Write a value to a GPIO."""
    if value == 1:
        switch.on()
    if value == 0:
        switch.off()


def read_input(sensor):
    """Read a value from a GPIO."""
    return sensor.value
