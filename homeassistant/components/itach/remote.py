"""Support for iTach IR devices."""

from collections.abc import Iterable
import logging
from typing import Any, override

import pyitachip2ir
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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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


def _format_command_value(value: str) -> str:
    """Format a command name or command data value."""
    value = value.strip()
    return value or EMPTY_COMMAND_PLACEHOLDER


def _format_command_table(commands: Iterable[dict[str, str]]) -> str:
    """Format YAML commands for pyitachip2ir."""
    return "".join(
        f"{_format_command_value(command[CONF_NAME])}\n"
        f"{_format_command_value(command[CONF_DATA])}\n"
        for command in commands
    )


def _setup_remote_entity(
    itachip2ir: Any, device_config: dict[str, Any]
) -> ITachIP2IRRemote:
    """Create an iTach remote entity from YAML device config."""
    name = device_config.get(CONF_NAME)
    modaddr = int(device_config.get(CONF_MODADDR, DEFAULT_MODADDR))
    connaddr = int(device_config.get(CONF_CONNADDR, DEFAULT_CONNADDR))
    ir_count = int(device_config.get(CONF_IR_COUNT, DEFAULT_IR_COUNT))
    command_table = _format_command_table(device_config[CONF_COMMANDS])

    itachip2ir.addDevice(name, modaddr, connaddr, command_table)
    return ITachIP2IRRemote(itachip2ir, name, ir_count)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ITach connection and devices."""
    itachip2ir = pyitachip2ir.ITachIP2IR(
        config.get(CONF_MAC), config[CONF_HOST], int(config[CONF_PORT])
    )

    if not itachip2ir.ready(CONNECT_TIMEOUT):
        _LOGGER.error("Unable to find iTach")
        return

    devices = [
        _setup_remote_entity(itachip2ir, device_config)
        for device_config in config[CONF_DEVICES]
    ]
    add_entities(devices, True)


class ITachIP2IRRemote(remote.RemoteEntity):
    """Device that sends commands to an ITachIP2IR device."""

    def __init__(self, itachip2ir: Any, name: str | None, ir_count: int) -> None:
        """Initialize device."""
        self.itachip2ir = itachip2ir
        self._attr_is_on = False
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._ir_count = ir_count or DEFAULT_IR_COUNT

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._attr_is_on = True
        self.itachip2ir.send(self.name, "ON", self._ir_count)
        self.schedule_update_ha_state()

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._attr_is_on = False
        self.itachip2ir.send(self.name, "OFF", self._ir_count)
        self.schedule_update_ha_state()

    @override
    def send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to one device."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        for single_command in command:
            self.itachip2ir.send(
                self.name, single_command, self._ir_count * num_repeats
            )

    def update(self) -> None:
        """Update the device."""
        self.itachip2ir.update()
