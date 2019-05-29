"""Support for Arduino-compatible Microcontrollers through Firmata."""
import ipaddress
import logging

import voluptuous as vol
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

from .board import FirmataBoard
from .const import (CONF_ARDUINO_WAIT, CONF_HANDSHAKE, CONF_INITIAL_STATE,
                    CONF_NEGATE_STATE, CONF_PIN, CONF_PORT, CONF_REMOTE,
                    CONF_SERIAL_PORT, CONF_SLEEP_TUNE, CONF_SWITCHES,
                    CONF_TYPE, CONF_TYPE_ANALOG, CONF_TYPE_DIGITAL, DOMAIN)

_LOGGER = logging.getLogger(__name__)

DATA_CONFIGS = 'board_configs'

SWITCH_SCHEMA = vol.Schema({
    vol.Required(CONF_PIN): cv.positive_int,
    vol.Required(CONF_TYPE): vol.All(vol.Any(CONF_TYPE_DIGITAL,
                                             CONF_TYPE_ANALOG), cv.string),
    vol.Optional(CONF_INITIAL_STATE, default=False): cv.boolean,
    vol.Optional(CONF_NEGATE_STATE, default=False): cv.boolean,
}, required=True, extra=vol.ALLOW_EXTRA)

BOARD_CONFIG_SCHEMA = vol.Schema(vol.All(
    {
        vol.Exclusive(CONF_REMOTE, 'connect_location'): {
            # Validate as IP address and then convert back to a string.
            vol.Required(CONF_HOST): vol.All(ipaddress.ip_address, cv.string),
            vol.Optional(CONF_PORT): cv.port,
            vol.Optional(CONF_HANDSHAKE): cv.string,
        },
        vol.Exclusive(CONF_SERIAL_PORT, 'connect_location'): cv.string,
        vol.Optional(CONF_ARDUINO_WAIT): cv.positive_int,
        vol.Optional(CONF_SLEEP_TUNE): vol.All(vol.Coerce(float),
                                               vol.Range(min=0.0001)),
        vol.Optional(CONF_SWITCHES): {cv.string: SWITCH_SCHEMA}
    },
    {
        # Require either a serial port or a host.
        vol.Required(vol.Any(CONF_REMOTE,
                             CONF_SERIAL_PORT)): vol.Any(cv.string, dict),
        vol.Optional(CONF_ARDUINO_WAIT): cv.positive_int,
        vol.Optional(CONF_SLEEP_TUNE): vol.All(vol.Coerce(float),
                                               vol.Range(min=0.0001)),
        vol.Optional(CONF_SWITCHES): {cv.string: SWITCH_SCHEMA}
    }
), required=True, extra=vol.ALLOW_EXTRA)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.string: BOARD_CONFIG_SCHEMA
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Firmata domain."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = {}

    for name in conf:
        board_conf = conf[name]

        board = FirmataBoard(hass, name, board_conf)

        if not await board.async_setup():
            return False

        hass.data[DOMAIN][name] = board

    hass.async_create_task(async_load_platform(hass, 'switch', DOMAIN, {},
                                               config))

    return True
