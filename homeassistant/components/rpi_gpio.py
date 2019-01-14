"""
Support for controlling GPIO pins of a Raspberry Pi.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rpi_gpio/
"""
import logging
import importlib

import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['RPi.GPIO==0.6.5',
                'OPi.GPIO==0.3.6']

_LOGGER = logging.getLogger(__name__)

CONF_BOARD_FAMILY = 'board_family'

DEFAULT_FAMILY = 'raspberry_pi'
FAMILY_LIBRARIES = {'raspberry_pi': 'RPi.GPIO',
                    'orange_pi': 'OPi.GPIO'}

DOMAIN = 'rpi_gpio'
LIBRARY = 'gpio_library'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_BOARD_FAMILY, default=DEFAULT_FAMILY): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


class UnknownBoardFamily(Exception):
    """board_family should be 'raspberry_pi' or 'orange_pi'."""

    pass


def setup(hass, base_config):
    """Set up the GPIO component."""
    hass.data[DOMAIN] = {}

    config = base_config.get(DOMAIN)
    family_name = config.get(CONF_BOARD_FAMILY, DEFAULT_FAMILY)
    lib_name = FAMILY_LIBRARIES.get(family_name)
    _LOGGER.info('Configured to use board family %s', family_name)
    _LOGGER.info('Will use %s as GPIO library', lib_name)
    if not lib_name:
        raise UnknownBoardFamily('Unknown board family: %s'
                                 % config.get(CONF_BOARD_FAMILY))
    hass.data[DOMAIN][LIBRARY] = importlib.import_module(lib_name)

    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        hass.data[DOMAIN][LIBRARY].cleanup()

    def prepare_gpio(event):
        """Stuff to do when home assistant starts."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)

    if family_name == 'orange_pi':
        hass.data[DOMAIN][LIBRARY].setmode(hass.data[DOMAIN][LIBRARY].SUNXI)
    else:
        hass.data[DOMAIN][LIBRARY].setmode(hass.data[DOMAIN][LIBRARY].BCM)

    return True


def setup_output(hass, port):
    """Set up a GPIO as output."""
    hass.data[DOMAIN][LIBRARY].setup(port, hass.data[DOMAIN][LIBRARY].OUT)


def setup_input(hass, port, pull_mode):
    """Set up a GPIO as input."""
    pull_mode = (hass.data[DOMAIN][LIBRARY].PUD_DOWN if pull_mode == 'DOWN'
                 else hass.data[DOMAIN][LIBRARY].PUD_UP)
    hass.data[DOMAIN][LIBRARY].setup(
        port, hass.data[DOMAIN][LIBRARY].IN, pull_mode)


def write_output(hass, port, value):
    """Write a value to a GPIO."""
    hass.data[DOMAIN][LIBRARY].output(port, value)


def read_input(hass, port):
    """Read a value from a GPIO."""
    return hass.data[DOMAIN][LIBRARY].input(port)


def edge_detect(hass, port, event_callback, bounce):
    """Add detection for RISING and FALLING events."""
    hass.data[DOMAIN][LIBRARY].add_event_detect(
        port,
        hass.data[DOMAIN][LIBRARY].BOTH,
        callback=event_callback,
        bouncetime=bounce)
