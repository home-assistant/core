"""Support for iTach IR devices."""

from collections.abc import Iterable
import logging
from typing import Any

from pyitach import ItachClient, ItachError
import voluptuous as vol

from homeassistant.components import remote
from homeassistant.components.remote import (
    ATTR_NUM_REPEATS,
    DEFAULT_NUM_REPEATS,
    PLATFORM_SCHEMA as REMOTE_PLATFORM_SCHEMA,
)
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    DEVICE_DEFAULT_NAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .client import async_create_client, async_send_command as async_send_itach_command
from .command import CommandParseError, ParsedItachCommand, parse_pronto_command

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 4998
CONNECT_TIMEOUT = 5000
DEFAULT_MODADDR = 1
DEFAULT_CONNADDR = 1
DEFAULT_IR_COUNT = 1

CONF_MODADDR = "modaddr"
CONF_CONNADDR = "connaddr"
CONF_COMMANDS = "commands"
CONF_DATA = "data"
CONF_IR_COUNT = "ir_count"

EMPTY_COMMAND_PLACEHOLDER = '""'

PLATFORM_SCHEMA = REMOTE_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MAC): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_DEVICES): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_MODADDR): cv.positive_int,
                    vol.Required(CONF_CONNADDR): cv.positive_int,
                    vol.Optional(CONF_IR_COUNT): cv.positive_int,
                    vol.Required(CONF_COMMANDS): vol.All(
                        cv.ensure_list,
                        [
                            {
                                vol.Required(CONF_NAME): cv.string,
                                vol.Required(CONF_DATA): cv.string,
                            }
                        ],
                    ),
                }
            ],
        ),
    }
)


def _format_command_name(value: str) -> str:
    """Format a legacy command name."""
    value = value.strip()
    return value or EMPTY_COMMAND_PLACEHOLDER


def _commands_from_config(
    commands: Iterable[dict[str, str]],
) -> dict[str, ParsedItachCommand]:
    """Parse legacy YAML commands keyed by command name."""
    return {
        _format_command_name(command[CONF_NAME]): parse_pronto_command(
            command[CONF_DATA]
        )
        for command in commands
    }


def _setup_remote_entity(
    client: ItachClient, device_config: dict[str, Any]
) -> ITachIP2IRRemote:
    """Create an iTach remote entity from YAML device config."""
    name = device_config.get(CONF_NAME)
    modaddr = int(device_config.get(CONF_MODADDR, DEFAULT_MODADDR))
    connaddr = int(device_config.get(CONF_CONNADDR, DEFAULT_CONNADDR))
    ir_count = int(device_config.get(CONF_IR_COUNT, DEFAULT_IR_COUNT))
    commands = _commands_from_config(device_config[CONF_COMMANDS])

    return ITachIP2IRRemote(client, name, modaddr, connaddr, ir_count, commands)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ITach connection and devices."""
    try:
        client = await async_create_client(
            config[CONF_HOST], int(config[CONF_PORT]), CONNECT_TIMEOUT / 1000
        )
    except ItachError:
        _LOGGER.error("Unable to find iTach")
        return

    try:
        devices = [
            _setup_remote_entity(client, device_config)
            for device_config in config[CONF_DEVICES]
        ]
    except CommandParseError as err:
        _LOGGER.error("Invalid iTach command data: %s", err)
        await client.close()
        return

    async def async_close_client(_event: Event[Any]) -> None:
        """Close the iTach client on Home Assistant stop."""
        await client.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_client)

    add_entities(devices, True)


class ITachIP2IRRemote(remote.RemoteEntity):
    """Device that sends commands to an ITachIP2IR device."""

    def __init__(
        self,
        client: ItachClient,
        name: str | None,
        modaddr: int,
        connaddr: int,
        ir_count: int,
        commands: dict[str, ParsedItachCommand],
    ) -> None:
        """Initialize device."""
        self._client = client
        self._attr_is_on = False
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._modaddr = modaddr
        self._connaddr = connaddr
        self._ir_count = ir_count or DEFAULT_IR_COUNT
        self._commands = commands

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._attr_is_on = True
        await self._async_send_named_command("ON", self._ir_count)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._attr_is_on = False
        await self._async_send_named_command("OFF", self._ir_count)
        self.async_write_ha_state()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to one device."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        for single_command in command:
            await self._async_send_named_command(
                single_command, self._ir_count * num_repeats
            )

    async def _async_send_named_command(self, command_name: str, repeat: int) -> None:
        """Send one named legacy command."""
        if (command := self._commands.get(command_name)) is None:
            raise HomeAssistantError(f"Command {command_name} is not configured")

        await async_send_itach_command(
            self._client,
            self._modaddr,
            self._connaddr,
            command,
            repeat,
        )
