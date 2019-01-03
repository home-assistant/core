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
                'OrangePi.GPIO==0.6.3']

_LOGGER = logging.getLogger(__name__)

CONF_BOARD_FAMILY = 'board_family'
CONF_BOARD = 'board'

DEFAULT_FAMILY = 'raspberry_pi'
FAMILY_LIBRARIES = {'raspberry_pi': 'RPi.GPIO',
                    'orange_pi': 'OPi.GPIO'}

ORANGEPI_BOARDS = {'zero': 'ZERO',
                   'r1': 'R1',
                   'zeroplus': 'ZEROPLUS',
                   'zeroplus2h5': 'ZEROPLUS2H5',
                   'zeroplus2h3': 'ZEROPLUS2H3',
                   'pcpplus': 'PCPCPLUS',
                   'one': 'ONE',
                   'lite': 'LITE',
                   'plus2e': 'PLUS2E',
                   'pc2': 'PC2',
                   'prime': 'PRIME',
                   }

DOMAIN = 'rpi_gpio'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_BOARD_FAMILY, default=DEFAULT_FAMILY): cv.string,
        vol.Optional(CONF_BOARD): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)

GPIO_LIBRARY = None


class UnknownBoardFamily(Exception):
    """board_family should be 'raspberry_pi' or 'orange_pi'"""


class UnknownOrangePiBoard(Exception):
    """'board' config item not set""" 


def setup(hass, base_config):
    """Set up the GPIO component."""
    global GPIO_LIBRARY

    config = base_config.get(DOMAIN)
    family_name = config.get(CONF_BOARD_FAMILY, DEFAULT_FAMILY)
    lib_name = FAMILY_LIBRARIES.get(family_name)
    _LOGGER.info('Configured to use board family %s', family_name)
    _LOGGER.info('Will use %s as GPIO library', lib_name)
    if not lib_name:
        raise UnknownBoardFamily('Unknown board family: %s'
                                 % config.get(CONF_BOARD_FAMILY))
    GPIO_LIBRARY = importlib.import_module(lib_name)

    # OrangePi GPIOS require knowledge of the specific board as well
    if family_name == 'orange_pi':
        board_name = config.get(CONF_BOARD)
        board = ORANGEPI_BOARDS.get(board_name)
        _LOGGER.info('OrangePi %s board specified', board_name)

        if not board_name:
            raise UnknownOrangePiBoard('You must specify a board type '
                                       'with the "board" configuration '
                                       'option.')
        GPIO_LIBRARY.setboard(getattr(GPIO_LIBRARY, board))

    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        GPIO_LIBRARY.cleanup()

    def prepare_gpio(event):
        """Stuff to do when home assistant starts."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)

    if family_name == 'orange_pi':
        GPIO_LIBRARY.setmode(GPIO_LIBRARY.BOARD)
    else:
        GPIO_LIBRARY.setmode(GPIO_LIBRARY.BCM)

    return True


def setup_output(port):
    """Set up a GPIO as output."""
    GPIO_LIBRARY.setup(port, GPIO_LIBRARY.OUT)


def setup_input(port, pull_mode):
    """Set up a GPIO as input."""
    pull_mode = (GPIO_LIBRARY.PUD_DOWN if pull_mode == 'DOWN'
                 else GPIO_LIBRARY.PUD_UP)
    GPIO_LIBRARY.setup(port, GPIO_LIBRARY.IN, pull_mode)


def write_output(port, value):
    """Write a value to a GPIO."""
    GPIO_LIBRARY.output(port, value)


def read_input(port):
    """Read a value from a GPIO."""
    return GPIO_LIBRARY.input(port)


def edge_detect(port, event_callback, bounce):
    """Add detection for RISING and FALLING events."""
    GPIO_LIBRARY.add_event_detect(
        port,
        GPIO_LIBRARY.BOTH,
        callback=event_callback,
        bouncetime=bounce)
