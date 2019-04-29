"""Support for controlling GPIO pins of a Raspberry Pi."""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_BINARY_SENSORS, CONF_SWITCHES)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['gpiozero==1.4.1']

_LOGGER = logging.getLogger(__name__)

CONF_BOUNCETIME = 'bouncetime'
CONF_INVERT_LOGIC = 'invert_logic'
CONF_PULL_MODE = 'pull_mode'

DEFAULT_BOUNCETIME = 50
DEFAULT_INVERT_LOGIC = False
DEFAULT_PULL_MODE = "UP"

DOMAIN = 'remote_rpi_gpio'

_SENSORS_SCHEMA = vol.Schema({
    cv.positive_int: cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_BINARY_SENSORS, default={}): _SENSORS_SCHEMA,
        vol.Optional(CONF_SWITCHES, default={}): _SENSORS_SCHEMA,
        vol.Optional(CONF_BOUNCETIME,
                     default=DEFAULT_BOUNCETIME): cv.positive_int,
        vol.Optional(CONF_INVERT_LOGIC,
                     default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): cv.string,
    })]),
}, extra=vol.ALLOW_EXTRA)


def setup(hass: HomeAssistant, config):
    """Set up the Raspberry Pi Remote GPIO component."""
    if DOMAIN not in config:
        # Skip setup if no configuration is present
        return True

    for remote_gpio in config[DOMAIN]:
        address = remote_gpio[CONF_HOST]
        pull_mode = remote_gpio[CONF_PULL_MODE]
        bouncetime = remote_gpio[CONF_BOUNCETIME]
        invert_logic = remote_gpio[CONF_INVERT_LOGIC]

        b_sensors = remote_gpio[CONF_BINARY_SENSORS]
        load_platform(hass,
                      'binary_sensor',
                      DOMAIN,
                      {'address': address,
                       'invert_logic': invert_logic,
                       'pull_mode': pull_mode,
                       'bouncetime': bouncetime,
                       'binary_sensors': b_sensors},
                      config)

        switches = remote_gpio[CONF_SWITCHES]
        load_platform(hass, 'switch',
                      DOMAIN,
                      {'address': address,
                       'invert_logic': invert_logic,
                       'switches': switches},
                      config)

    return True


def setup_output(address, port, invert_logic):
    """Set up a GPIO as output."""
    from gpiozero import LED
    from gpiozero.pins.pigpio import PiGPIOFactory  # noqa: E501 pylint: disable=import-error

    try:
        return LED(port, active_high=invert_logic,
                   pin_factory=PiGPIOFactory(address))
    except (ValueError, IndexError, KeyError):
        return None


def setup_input(address, port, pull_mode, bouncetime):
    """Set up a GPIO as input."""
    from gpiozero import Button
    from gpiozero.pins.pigpio import PiGPIOFactory

    if pull_mode == "UP":
        pull_gpio_up = True
    elif pull_mode == "DOWN":
        pull_gpio_up = False

    try:
        return Button(port,
                      pull_up=pull_gpio_up,
                      bounce_time=bouncetime,
                      pin_factory=PiGPIOFactory(address))
    except (ValueError, IndexError, KeyError, IOError):
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
