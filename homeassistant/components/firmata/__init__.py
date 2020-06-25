"""Support for Arduino-compatible Microcontrollers through Firmata."""
from copy import copy
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import config_validation as cv

from . import config_flow  # noqa: F401
from .board import FirmataBoard
from .const import (
    CONF_ARDUINO_INSTANCE_ID,
    CONF_ARDUINO_WAIT,
    CONF_BINARY_SENSORS,
    CONF_INITIAL_STATE,
    CONF_NEGATE_STATE,
    CONF_PIN,
    CONF_PIN_MODE,
    CONF_SAMPLING_INTERVAL,
    CONF_SERIAL_BAUD_RATE,
    CONF_SERIAL_PORT,
    CONF_SLEEP_TUNE,
    CONF_SWITCHES,
    DOMAIN,
    PIN_MODE_INPUT,
    PIN_MODE_OUTPUT,
    PIN_MODE_PULLUP,
)

_LOGGER = logging.getLogger(__name__)

DATA_CONFIGS = "board_configs"

ANALOG_PIN_SCHEMA = vol.All(cv.string, vol.Match(r"^A[0-9]+$"))

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_PIN): vol.Any(cv.positive_int, ANALOG_PIN_SCHEMA),
        # will be analog mode in future too
        vol.Required(CONF_PIN_MODE): PIN_MODE_OUTPUT,
        vol.Optional(CONF_INITIAL_STATE, default=False): cv.boolean,
        vol.Optional(CONF_NEGATE_STATE, default=False): cv.boolean,
    },
    required=True,
    extra=vol.ALLOW_EXTRA,
)

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_PIN): vol.Any(cv.positive_int, ANALOG_PIN_SCHEMA),
        # will be analog mode in future too
        vol.Required(CONF_PIN_MODE): vol.Any(PIN_MODE_INPUT, PIN_MODE_PULLUP),
        vol.Optional(CONF_NEGATE_STATE, default=False): cv.boolean,
    },
    required=True,
    extra=vol.ALLOW_EXTRA,
)

BOARD_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): cv.string,
        vol.Optional(CONF_SERIAL_BAUD_RATE): cv.positive_int,
        vol.Optional(CONF_ARDUINO_INSTANCE_ID): cv.positive_int,
        vol.Optional(CONF_ARDUINO_WAIT): cv.positive_int,
        vol.Optional(CONF_SLEEP_TUNE): vol.All(
            vol.Coerce(float), vol.Range(min=0.0001)
        ),
        vol.Optional(CONF_SAMPLING_INTERVAL): cv.positive_int,
        vol.Optional(CONF_SWITCHES): [SWITCH_SCHEMA],
        vol.Optional(CONF_BINARY_SENSORS): [BINARY_SENSOR_SCHEMA],
    },
    required=True,
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [BOARD_CONFIG_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Set up the Firmata domain."""
    # Delete all entries if domain removed from config
    if DOMAIN not in config:
        if hass.config_entries.async_entries(DOMAIN):
            for entry in hass.config_entries.async_entries(DOMAIN):
                await hass.config_entries.async_remove(entry.entry_id)
        return True

    # Delete specific entries that no longer exist in the config
    if hass.config_entries.async_entries(DOMAIN):
        for entry in hass.config_entries.async_entries(DOMAIN):
            remove = True
            for board in config[DOMAIN]:
                if entry.data[CONF_SERIAL_PORT] == board[CONF_SERIAL_PORT]:
                    remove = False
                    break
            if remove:
                await hass.config_entries.async_remove(entry.entry_id)

    # Setup new entries and update old entries
    for board in config[DOMAIN]:
        firmata_config = copy(board)
        existing_entry = False
        for entry in hass.config_entries.async_entries(DOMAIN):
            if board[CONF_SERIAL_PORT] == entry.data[CONF_SERIAL_PORT]:
                existing_entry = True
                firmata_config[CONF_NAME] = entry.data[CONF_NAME]
                hass.config_entries.async_update_entry(entry, data=firmata_config)
                break
        if not existing_entry:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data=firmata_config,
                )
            )

    async def handle_shutdown(event):
        """Handle shutdown of baords when Home Assistant shuts down."""
        for board in hass.data[DOMAIN]:
            await hass.data[DOMAIN][board].async_reset()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_shutdown)

    return True


async def async_setup_entry(hass, config_entry):
    """Set up a Firmata board for a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    _LOGGER.debug(
        "Setting up Firmata id %s, name %s, config %s",
        config_entry.entry_id,
        config_entry.data[CONF_NAME],
        config_entry.data,
    )

    board = FirmataBoard(hass, config_entry)

    if not await board.async_setup():
        return False

    hass.data[DOMAIN][config_entry.entry_id] = board

    await board.async_update_device_registry()
    if CONF_BINARY_SENSORS in config_entry.data:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor")
        )
    if CONF_SWITCHES in config_entry.data:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, "switch")
        )
    return True


async def async_unload_entry(hass, config_entry) -> None:
    """Shutdown and close a Firmata board for a config entry."""
    _LOGGER.info("Closing Firmata board %s", config_entry.data[CONF_NAME])
    if CONF_BINARY_SENSORS in config_entry.data:
        await hass.config_entries.async_forward_entry_unload(
            config_entry, "binary_sensor"
        )
    if CONF_SWITCHES in config_entry.data:
        await hass.config_entries.async_forward_entry_unload(config_entry, "switch")
    await hass.data[DOMAIN].pop(config_entry.entry_id).async_reset()
    return True
