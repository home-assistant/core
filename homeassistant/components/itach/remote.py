"""Support for iTach IR devices."""
from __future__ import annotations

import logging

import pyitachip2ir
import voluptuous as vol

from homeassistant.components import remote
from homeassistant.components.remote import (
    ATTR_NUM_REPEATS,
    DEFAULT_NUM_REPEATS,
    PLATFORM_SCHEMA,
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
import homeassistant.helpers.config_validation as cv
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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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

    devices = []
    for data in config[CONF_DEVICES]:
        name = data.get(CONF_NAME)
        modaddr = int(data.get(CONF_MODADDR, DEFAULT_MODADDR))
        connaddr = int(data.get(CONF_CONNADDR, DEFAULT_CONNADDR))
        ir_count = int(data.get(CONF_IR_COUNT, DEFAULT_IR_COUNT))
        cmddatas = ""
        for cmd in data.get(CONF_COMMANDS):
            cmdname = cmd[CONF_NAME].strip()
            if not cmdname:
                cmdname = '""'
            cmddata = cmd[CONF_DATA].strip()
            if not cmddata:
                cmddata = '""'
            cmddatas += f"{cmdname}\n{cmddata}\n"
        itachip2ir.addDevice(name, modaddr, connaddr, cmddatas)
        devices.append(ITachIP2IRRemote(itachip2ir, name, ir_count))
    add_entities(devices, True)


class ITachIP2IRRemote(remote.RemoteEntity):
    """Device that sends commands to an ITachIP2IR device."""

    def __init__(self, itachip2ir, name, ir_count):
        """Initialize device."""
        self.itachip2ir = itachip2ir
        self._power = False
        self._name = name or DEVICE_DEFAULT_NAME
        self._ir_count = ir_count or DEFAULT_IR_COUNT

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._power

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._power = True
        self.itachip2ir.send(self._name, "ON", self._ir_count)
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._power = False
        self.itachip2ir.send(self._name, "OFF", self._ir_count)
        self.schedule_update_ha_state()

    def send_command(self, command, **kwargs):
        """Send a command to one device."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        for single_command in command:
            self.itachip2ir.send(
                self._name, single_command, self._ir_count * num_repeats
            )

    def update(self):
        """Update the device."""
        self.itachip2ir.update()
