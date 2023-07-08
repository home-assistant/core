"""Allows to configure custom shell commands to turn a value for a sensor."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
import json
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    STATE_CLASSES_SCHEMA,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.template import Template
from homeassistant.helpers.template_entity import ManualTriggerEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN, LOGGER
from .utils import check_output_or_log

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
    if sensor_config := config:
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_sensor",
            breaks_in_ha_version="2023.12.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_platform_yaml",
            translation_placeholders={"platform": SENSOR_DOMAIN},
        )
    if discovery_info:
        sensor_config = discovery_info

    name: str = sensor_config[CONF_NAME]
    command: str = sensor_config[CONF_COMMAND]
    unit: str | None = sensor_config.get(CONF_UNIT_OF_MEASUREMENT)
    value_template: Template | None = sensor_config.get(CONF_VALUE_TEMPLATE)
    command_timeout: int = sensor_config[CONF_COMMAND_TIMEOUT]
    unique_id: str | None = sensor_config.get(CONF_UNIQUE_ID)
    if value_template is not None:
        value_template.hass = hass
    json_attributes: list[str] | None = sensor_config.get(CONF_JSON_ATTRIBUTES)
    scan_interval: timedelta = sensor_config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    state_class: SensorStateClass | None = sensor_config.get(CONF_STATE_CLASS)
    data = CommandSensorData(hass, command, command_timeout)

    trigger_entity_config = {
        CONF_UNIQUE_ID: unique_id,
        CONF_NAME: Template(name, hass),
        CONF_DEVICE_CLASS: sensor_config.get(CONF_DEVICE_CLASS),
    }

    async_add_entities(
        [
            CommandSensor(
                data,
                trigger_entity_config,
                unit,
                state_class,
                value_template,
                json_attributes,
                scan_interval,
            )
        ]
    )


class CommandSensor(ManualTriggerEntity, SensorEntity):
    """Representation of a sensor that is using shell commands."""

    _attr_should_poll = False

    def __init__(
        self,
        data: CommandSensorData,
        config: ConfigType,
        unit_of_measurement: str | None,
        state_class: SensorStateClass | None,
        value_template: Template | None,
        json_attributes: list[str] | None,
        scan_interval: timedelta,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(self.hass, config)
        self.data = data
        self._attr_extra_state_attributes = {}
        self._json_attributes = json_attributes
        self._attr_native_value = None
        self._value_template = value_template
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_state_class = state_class
        self._scan_interval = scan_interval
        self._process_updates: asyncio.Lock | None = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return cast(dict, self._attr_extra_state_attributes)

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self._update_entity_state(None)
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._update_entity_state,
                self._scan_interval,
                name=f"Command Line Sensor - {self.name}",
                cancel_on_shutdown=True,
            ),
        )

    async def _update_entity_state(self, now) -> None:
        """Update the state of the entity."""
        if self._process_updates is None:
            self._process_updates = asyncio.Lock()
        if self._process_updates.locked():
            LOGGER.warning(
                "Updating Command Line Sensor %s took longer than the scheduled update interval %s",
                self.name,
                self._scan_interval,
            )
            return

        async with self._process_updates:
            await self._async_update()

    async def _async_update(self) -> None:
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
                        LOGGER.warning("JSON result was not a dictionary")
                except ValueError:
                    LOGGER.warning("Unable to parse output as JSON: %s", value)
            else:
                LOGGER.warning("Empty reply found when expecting JSON data")
            if self._value_template is None:
                self._attr_native_value = None
                self._process_manual_data(value)
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
        self._process_manual_data(value)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._update_entity_state(dt_util.now())


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
                LOGGER.exception("Error rendering command template: %s", ex)
                return
        else:
            rendered_args = None

        if rendered_args == args:
            # No template used. default behavior
            pass
        else:
            # Template used. Construct the string used in the shell
            command = f"{prog} {rendered_args}"

        LOGGER.debug("Running command: %s", command)
        self.value = check_output_or_log(command, self.timeout)
