"""Support for the Arduino-compatible Microcontrollers through Firmata"""
import asyncio
import ipaddress
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant.helpers import (config_validation as cv, device_registry as dr)
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN, CONF_NAME, CONF_PORT, CONF_HANDSHAKE, CONF_SERIAL_PORT
from .board import FirmataBoard

_LOGGER = logging.getLogger(__name__)

CONF_BOARDS = "boards"

DATA_CONFIGS = 'board_configs'

BOARD_CONFIG_SCHEMA = vol.Schema(vol.All(
    {
        # Validate as IP address and then convert back to a string.
        vol.Required(CONF_NAME): cv.string,
        vol.Exclusive(CONF_HOST, 'connect_location'): vol.All(ipaddress.ip_address, cv.string),
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_HANDSHAKE): cv.string,
        vol.Exclusive(CONF_SERIAL_PORT, 'connect_location'): cv.string,
    },
    {
        vol.Required(CONF_NAME): cv.string,
        # Require either a serial port or a host/port
        vol.Required(vol.Any(CONF_HOST, CONF_SERIAL_PORT)): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_HANDSHAKE): cv.string,
    }
), required=True, extra=vol.ALLOW_EXTRA)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_BOARDS):
            vol.All(cv.ensure_list, [BOARD_CONFIG_SCHEMA]),
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Firmata platform."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = {}

    boards = conf[CONF_BOARDS]

    for board_conf in boards:
        name = board_conf[CONF_NAME]
        
        conf_data = {
          'name': board_conf[CONF_NAME]
		}
        if CONF_HOST in board_conf:
            conf_data['ip_address'] = board_conf[CONF_HOST]
            if CONF_PORT in board_conf:
                conf_data['ip_port'] = board_conf[CONF_PORT]
            if CONF_HANDSHAKE in board_conf:
                conf_data['ip_handshake'] = board_conf[CONF_HANDSHAKE]
        else:
            conf_data['com_port'] = board_conf[CONF_SERIAL_PORT]

        board = FirmataBoard(hass, conf_data)

        if not await board.async_setup():
            return False

        hass.data[DOMAIN][name] = board
        
    hass.async_create_task(async_load_platform(hass, 'switch', DOMAIN, {}, config))
        
    return True
