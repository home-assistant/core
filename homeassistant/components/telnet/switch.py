"""Support for switch controlled using a telnet connection."""
from __future__ import annotations

from datetime import timedelta
import logging
import telnetlib
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COMMAND_STATE,
    CONF_NAME,
    CONF_PORT,
    CONF_RESOURCE,
    CONF_SWITCHES,
    CONF_TIMEOUT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 23
DEFAULT_TIMEOUT = 0.2

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND_OFF): cv.string,
        vol.Required(CONF_COMMAND_ON): cv.string,
        vol.Required(CONF_RESOURCE): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_COMMAND_STATE): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(float),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA)}
)

SCAN_INTERVAL = timedelta(seconds=10)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Find and return switches controlled by telnet commands."""
    devices: dict[str, Any] = config[CONF_SWITCHES]
    switches = []

    for object_id, device_config in devices.items():
        value_template: Template | None = device_config.get(CONF_VALUE_TEMPLATE)

        if value_template is not None:
            value_template.hass = hass

        switches.append(
            TelnetSwitch(
                object_id,
                device_config[CONF_RESOURCE],
                device_config[CONF_PORT],
                device_config.get(CONF_NAME, object_id),
                device_config[CONF_COMMAND_ON],
                device_config[CONF_COMMAND_OFF],
                device_config.get(CONF_COMMAND_STATE),
                value_template,
                device_config[CONF_TIMEOUT],
            )
        )

    if not switches:
        _LOGGER.error("No switches added")
        return

    add_entities(switches)


class TelnetSwitch(SwitchEntity):
    """Representation of a switch that can be toggled using telnet commands."""

    def __init__(
        self,
        object_id: str,
        resource: str,
        port: int,
        friendly_name: str,
        command_on: str,
        command_off: str,
        command_state: str | None,
        value_template: Template | None,
        timeout: float,
    ) -> None:
        """Initialize the switch."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._resource = resource
        self._port = port
        self._attr_name = friendly_name
        self._attr_is_on = False
        self._command_on = command_on
        self._command_off = command_off
        self._command_state = command_state
        self._value_template = value_template
        self._timeout = timeout
        self._attr_should_poll = bool(command_state)
        self._attr_assumed_state = bool(command_state is None)

    def _telnet_command(self, command: str) -> str | None:
        try:
            telnet = telnetlib.Telnet(self._resource, self._port)
            telnet.write(command.encode("ASCII") + b"\r")
            response = telnet.read_until(b"\r", timeout=self._timeout)
        except OSError as error:
            _LOGGER.error(
                'Command "%s" failed with exception: %s', command, repr(error)
            )
            return None
        _LOGGER.debug("telnet response: %s", response.decode("ASCII").strip())
        return response.decode("ASCII").strip()

    def update(self) -> None:
        """Update device state."""
        if not self._command_state:
            return
        response = self._telnet_command(self._command_state)
        if response and self._value_template:
            rendered = self._value_template.render_with_possible_json_value(response)
        else:
            _LOGGER.warning("Empty response for command: %s", self._command_state)
            return None
        self._attr_is_on = rendered == "True"

    def turn_on(self, **kwargs) -> None:
        """Turn the device on."""
        self._telnet_command(self._command_on)
        if self.assumed_state:
            self._attr_is_on = True
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        self._telnet_command(self._command_off)
        if self.assumed_state:
            self._attr_is_on = False
            self.schedule_update_ha_state()
