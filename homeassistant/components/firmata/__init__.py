"""Support for Arduino-compatible Microcontrollers through Firmata."""

from copy import copy
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_LIGHTS,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
    CONF_PIN,
    CONF_SENSORS,
    CONF_SWITCHES,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .board import FirmataBoard
from .const import (
    CONF_ARDUINO_INSTANCE_ID,
    CONF_ARDUINO_WAIT,
    CONF_DIFFERENTIAL,
    CONF_INITIAL_STATE,
    CONF_NEGATE_STATE,
    CONF_PIN_MODE,
    CONF_PLATFORM_MAP,
    CONF_SAMPLING_INTERVAL,
    CONF_SERIAL_BAUD_RATE,
    CONF_SERIAL_PORT,
    CONF_SLEEP_TUNE,
    DOMAIN,
    FIRMATA_MANUFACTURER,
    PIN_MODE_ANALOG,
    PIN_MODE_INPUT,
    PIN_MODE_OUTPUT,
    PIN_MODE_PULLUP,
    PIN_MODE_PWM,
)

_LOGGER = logging.getLogger(__name__)

DATA_CONFIGS = "board_configs"

ANALOG_PIN_SCHEMA = vol.All(cv.string, vol.Match(r"^A[0-9]+$"))

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        # Both digital and analog pins may be used as digital output
        vol.Required(CONF_PIN): vol.Any(cv.positive_int, ANALOG_PIN_SCHEMA),
        vol.Required(CONF_PIN_MODE): PIN_MODE_OUTPUT,
        vol.Optional(CONF_INITIAL_STATE, default=False): cv.boolean,
        vol.Optional(CONF_NEGATE_STATE, default=False): cv.boolean,
    },
    required=True,
)

LIGHT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        # Both digital and analog pins may be used as PWM/analog output
        vol.Required(CONF_PIN): vol.Any(cv.positive_int, ANALOG_PIN_SCHEMA),
        vol.Required(CONF_PIN_MODE): PIN_MODE_PWM,
        vol.Optional(CONF_INITIAL_STATE, default=0): cv.positive_int,
        vol.Optional(CONF_MINIMUM, default=0): cv.positive_int,
        vol.Optional(CONF_MAXIMUM, default=255): cv.positive_int,
    },
    required=True,
)

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        # Both digital and analog pins may be used as digital input
        vol.Required(CONF_PIN): vol.Any(cv.positive_int, ANALOG_PIN_SCHEMA),
        vol.Required(CONF_PIN_MODE): vol.Any(PIN_MODE_INPUT, PIN_MODE_PULLUP),
        vol.Optional(CONF_NEGATE_STATE, default=False): cv.boolean,
    },
    required=True,
)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        # Currently only analog input sensor is implemented
        vol.Required(CONF_PIN): ANALOG_PIN_SCHEMA,
        vol.Required(CONF_PIN_MODE): PIN_MODE_ANALOG,
        # Default differential is 40 to avoid a flood of messages on initial setup
        # in case pin is unplugged. Firmata responds really really fast
        vol.Optional(CONF_DIFFERENTIAL, default=40): vol.All(
            cv.positive_int, vol.Range(min=1)
        ),
    },
    required=True,
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
        vol.Optional(CONF_LIGHTS): [LIGHT_SCHEMA],
        vol.Optional(CONF_BINARY_SENSORS): [BINARY_SENSOR_SCHEMA],
        vol.Optional(CONF_SENSORS): [SENSOR_SCHEMA],
    },
    required=True,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [BOARD_CONFIG_SCHEMA])}, extra=vol.ALLOW_EXTRA
)

type FirmataConfigEntry = ConfigEntry[FirmataBoard]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Firmata domain."""
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
                    context={"source": SOURCE_IMPORT},
                    data=firmata_config,
                )
            )

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: FirmataConfigEntry
) -> bool:
    """Set up a Firmata board for a config entry."""
    _LOGGER.debug(
        "Setting up Firmata id %s, name %s, config %s",
        config_entry.entry_id,
        config_entry.data[CONF_NAME],
        config_entry.data,
    )

    board = FirmataBoard(config_entry.data)

    if not await board.async_setup():
        return False

    config_entry.runtime_data = board

    async def handle_shutdown(event) -> None:
        """Handle shutdown of board when Home Assistant shuts down."""
        await board.async_reset()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_shutdown)
    )

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections=set(),
        identifiers={(DOMAIN, board.name)},
        manufacturer=FIRMATA_MANUFACTURER,
        name=board.name,
        sw_version=board.firmware_version,
    )

    await hass.config_entries.async_forward_entry_setups(
        config_entry,
        [
            platform
            for conf, platform in CONF_PLATFORM_MAP.items()
            if conf in config_entry.data
        ],
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: FirmataConfigEntry
) -> bool:
    """Shutdown and close a Firmata board for a config entry."""
    _LOGGER.debug("Closing Firmata board %s", config_entry.data[CONF_NAME])
    results: list[bool] = []
    if platforms := [
        platform
        for conf, platform in CONF_PLATFORM_MAP.items()
        if conf in config_entry.data
    ]:
        results.append(
            await hass.config_entries.async_unload_platforms(config_entry, platforms)
        )
    results.append(await config_entry.runtime_data.async_reset())

    return False not in results
