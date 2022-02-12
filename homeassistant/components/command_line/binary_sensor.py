"""Support for custom shell commands to retrieve values."""
from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.reload import setup_reload_service
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN, PLATFORMS
from .sensor import CommandSensorData

DEFAULT_NAME = "Binary Command Sensor"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"

SCAN_INTERVAL = timedelta(seconds=60)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Command line Binary Sensor."""

    setup_reload_service(hass, DOMAIN, PLATFORMS)

    name: str = config[CONF_NAME]
    command: str = config[CONF_COMMAND]
    payload_off: str = config[CONF_PAYLOAD_OFF]
    payload_on: str = config[CONF_PAYLOAD_ON]
    device_class: str | None = config.get(CONF_DEVICE_CLASS)
    value_template: Template | None = config.get(CONF_VALUE_TEMPLATE)
    command_timeout: int = config[CONF_COMMAND_TIMEOUT]
    unique_id: str | None = config.get(CONF_UNIQUE_ID)
    if value_template is not None:
        value_template.hass = hass
    data = CommandSensorData(hass, command, command_timeout)

    add_entities(
        [
            CommandBinarySensor(
                data,
                name,
                device_class,
                payload_on,
                payload_off,
                value_template,
                unique_id,
            )
        ],
        True,
    )


class CommandBinarySensor(BinarySensorEntity):
    """Representation of a command line binary sensor."""

    def __init__(
        self,
        data: CommandSensorData,
        name: str,
        device_class: str | None,
        payload_on: str,
        payload_off: str,
        value_template: Template | None,
        unique_id: str | None,
    ) -> None:
        """Initialize the Command line binary sensor."""
        self.data = data
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_is_on = None
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._value_template = value_template
        self._attr_unique_id = unique_id

    def update(self) -> None:
        """Get the latest data and updates the state."""
        self.data.update()
        value = self.data.value

        if self._value_template is not None:
            value = self._value_template.render_with_possible_json_value(value, False)
        if value == self._payload_on:
            self._attr_is_on = True
        elif value == self._payload_off:
            self._attr_is_on = False
