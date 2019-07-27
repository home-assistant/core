"""Support for Arduino-compatible Microcontrollers through Firmata."""
import ipaddress
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, CONF_NAME
from homeassistant.helpers import config_validation as cv

from .board import FirmataBoard
from . import config_flow  # noqa: F401
from .const import (CONF_ARDUINO_WAIT, CONF_HANDSHAKE, CONF_INITIAL_STATE,
                    CONF_NEGATE_STATE, CONF_PIN, CONF_PORT, CONF_REMOTE,
                    CONF_SERIAL_PORT, CONF_SLEEP_TUNE, CONF_SWITCHES,
                    CONF_PIN_MODE, CONF_PIN_MODE_OUTPUT, CONF_PIN_MODE_INPUT,
                    CONF_PIN_MODE_PULLUP, CONF_BINARY_SENSORS,
                    CONF_SAMPLING_INTERVAL, DOMAIN)

_LOGGER = logging.getLogger(__name__)

DATA_CONFIGS = 'board_configs'

ANALOG_PIN_SCHEMA = vol.All(cv.string, vol.Match(r'^A[0-9]+$'))

SWITCH_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_PIN): vol.Any(cv.positive_int, ANALOG_PIN_SCHEMA),
    # will be analog mode in future too
    vol.Required(CONF_PIN_MODE): vol.All(CONF_PIN_MODE_OUTPUT, cv.string),
    vol.Optional(CONF_INITIAL_STATE, default=False): cv.boolean,
    vol.Optional(CONF_NEGATE_STATE, default=False): cv.boolean
}, required=True, extra=vol.ALLOW_EXTRA)

BINARY_SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_PIN): vol.Any(cv.positive_int, ANALOG_PIN_SCHEMA),
    # will be analog mode in future too
    vol.Required(CONF_PIN_MODE): vol.All(vol.Any(CONF_PIN_MODE_INPUT,
                                                 CONF_PIN_MODE_PULLUP),
                                         cv.string),
    vol.Optional(CONF_NEGATE_STATE, default=False): cv.boolean
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
        vol.Optional(CONF_SAMPLING_INTERVAL): cv.positive_int,
        vol.Optional(CONF_SWITCHES): [SWITCH_SCHEMA],
        vol.Optional(CONF_BINARY_SENSORS): [BINARY_SENSOR_SCHEMA]
    },
    {
        # Require either a serial port or a host.
        vol.Required(vol.Any(CONF_REMOTE,
                             CONF_SERIAL_PORT)): vol.Any(cv.string, dict),
        vol.Optional(CONF_ARDUINO_WAIT): cv.positive_int,
        vol.Optional(CONF_SLEEP_TUNE): vol.All(vol.Coerce(float),
                                               vol.Range(min=0.0001)),
        vol.Optional(CONF_SAMPLING_INTERVAL): cv.positive_int,
        vol.Optional(CONF_SWITCHES): [SWITCH_SCHEMA],
        vol.Optional(CONF_BINARY_SENSORS): [BINARY_SENSOR_SCHEMA]
    }
), required=True, extra=vol.ALLOW_EXTRA)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: [BOARD_CONFIG_SCHEMA]
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Firmata domain."""
    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        for board in config[DOMAIN]:
            firmata_config = board
            hass.async_create_task(hass.config_entries.flow.async_init(
                DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
                data=firmata_config
            ))
    return True


async def async_setup_entry(hass, config_entry):
    """Set up a Firmata board for a config entry.

    Load config, group, light and sensor data for server information.
    Start websocket for push notification of state changes from deCONZ.
    """
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if not config_entry.options:
        await async_populate_options(hass, config_entry)

    board = FirmataBoard(hass, config_entry)

    if not await board.async_setup():
        return False

    hass.data[DOMAIN][board.name] = board

    await board.async_update_device_registry()
    if CONF_BINARY_SENSORS in config_entry.data:
        hass.async_add_job(hass.config_entries.async_forward_entry_setup(
            config_entry, 'binary_sensor'))
    if CONF_SWITCHES in config_entry.data:
        hass.async_add_job(hass.config_entries.async_forward_entry_setup(
            config_entry, 'switch'))
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, board.async_reset)
    return True


async def async_populate_options(hass, config_entry):
    """Populate default options for board.

    Called by setup_entry and unload_entry.
    Makes sure there is always one board available.
    """
    options = {}
    hass.config_entries.async_update_entry(config_entry, options=options)
