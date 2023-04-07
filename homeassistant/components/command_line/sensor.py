"""Allows to configure custom shell commands to turn a value for a sensor."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import json
import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    STATE_CLASSES_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN, PLATFORMS
from .utils import check_output_or_log

_LOGGER = logging.getLogger(__name__)

CONF_JSON_ATTRIBUTES = "json_attributes"

DEFAULT_NAME = "Command Sensor"

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND): cv.string,
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_JSON_ATTRIBUTES): cv.ensure_list_csv,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Command Sensor."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    name: str = config[CONF_NAME]
    command: str = config[CONF_COMMAND]
    unit: str | None = config.get(CONF_UNIT_OF_MEASUREMENT)
    value_template: Template | None = config.get(CONF_VALUE_TEMPLATE)
    command_timeout: int = config[CONF_COMMAND_TIMEOUT]
    unique_id: str | None = config.get(CONF_UNIQUE_ID)
    if value_template is not None:
        value_template.hass = hass
    json_attributes: list[str] | None = config.get(CONF_JSON_ATTRIBUTES)
    data = CommandSensorData(hass, command, command_timeout)

    async_add_entities(
        [
            CommandSensor(
                data,
                name,
                unit,
                value_template,
                json_attributes,
                unique_id,
            )
        ],
        True,
    )


class CommandSensor(SensorEntity):
    """Representation of a sensor that is using shell commands."""

    def __init__(
        self,
        data: CommandSensorData,
        name: str,
        unit_of_measurement: str | None,
        value_template: Template | None,
        json_attributes: list[str] | None,
        unique_id: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._attr_name = name
        self.data = data
        self._attr_extra_state_attributes = {}
        self._json_attributes = json_attributes
        self._attr_native_value = None
        self._value_template = value_template
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_unique_id = unique_id

    async def async_update(self) -> None:
        """Get the latest data and updates the state."""
        await self.hass.async_add_executor_job(self.data.update)
        value = self.data.value

        if self._json_attributes:
            self._attr_extra_state_attributes = {}
            if value:
                try:
                    json_dict = json.loads(value)
                    if isinstance(json_dict, Mapping):
                        self._attr_extra_state_attributes = {
                            k: json_dict[k]
                            for k in self._json_attributes
                            if k in json_dict
                        }
                    else:
                        _LOGGER.warning("JSON result was not a dictionary")
                except ValueError:
                    _LOGGER.warning("Unable to parse output as JSON: %s", value)
            else:
                _LOGGER.warning("Empty reply found when expecting JSON data")
            if self._value_template is None:
                self._attr_native_value = None
                return

        if self._value_template is not None:
            self._attr_native_value = (
                self._value_template.async_render_with_possible_json_value(
                    value,
                    None,
                )
            )
        else:
            self._attr_native_value = value


class CommandSensorData:
    """The class for handling the data retrieval."""

    def __init__(self, hass: HomeAssistant, command: str, command_timeout: int) -> None:
        """Initialize the data object."""
        self.value: str | None = None
        self.hass = hass
        self.command = command
        self.timeout = command_timeout

    def update(self) -> None:
        """Get the latest data with a shell command."""
        command = self.command

        if " " not in command:
            prog = command
            args = None
            args_compiled = None
        else:
            prog, args = command.split(" ", 1)
            args_compiled = Template(args, self.hass)

        if args_compiled:
            try:
                args_to_render = {"arguments": args}
                rendered_args = args_compiled.render(args_to_render)
            except TemplateError as ex:
                _LOGGER.exception("Error rendering command template: %s", ex)
                return
        else:
            rendered_args = None

        if rendered_args == args:
            # No template used. default behavior
            pass
        else:
            # Template used. Construct the string used in the shell
            command = f"{prog} {rendered_args}"

        _LOGGER.debug("Running command: %s", command)
        self.value = check_output_or_log(command, self.timeout)
