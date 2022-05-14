"""Support for custom shell commands to retrieve values."""
from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_PLATFORM,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN
from .sensor import CommandSensorData

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Command line Binary Sensor."""
    _LOGGER.warning(
        # Command Line config flow added in 2022.6 and should be removed in 2022.8
        "Configuration of the Command Line Binary Sensor platform in YAML is deprecated"
        "and will be removed in Home Assistant 2022.8; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )

    value_template: Template | None = config.get(CONF_VALUE_TEMPLATE)

    new_config = {
        **config,
        CONF_VALUE_TEMPLATE: value_template.template if value_template else None,
        CONF_PLATFORM: Platform.BINARY_SENSOR,
    }

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=new_config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Command Line Binary Sensor entry."""

    name: str = entry.options[CONF_NAME]
    command: str = entry.options[CONF_COMMAND]
    payload_off: str = entry.options[CONF_PAYLOAD_OFF]
    payload_on: str = entry.options[CONF_PAYLOAD_ON]
    device_class: str | None = entry.options.get(CONF_DEVICE_CLASS)
    value_template: Template | str | None = entry.options.get(CONF_VALUE_TEMPLATE)
    command_timeout: int = entry.options[CONF_COMMAND_TIMEOUT]
    unique_id: str | None = entry.options.get(CONF_UNIQUE_ID)
    if value_template is not None:
        value_template = Template(value_template)
        value_template.hass = hass
    data = CommandSensorData(hass, command, command_timeout)

    async_add_entities(
        [
            CommandBinarySensor(
                data,
                name,
                device_class,
                payload_on,
                payload_off,
                value_template,
                unique_id,
                entry.entry_id,
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
        entry_id: str,
    ) -> None:
        """Initialize the Command line binary sensor."""
        self.data = data
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_is_on = None
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._value_template = value_template
        self._attr_unique_id = unique_id if unique_id else entry_id

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
