"""Allows to configure custom shell commands to turn a value for a sensor."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta
import json
from typing import Any, cast

from jsonpath import jsonpath

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor.helpers import async_parse_date_datetime
from homeassistant.const import (
    CONF_COMMAND,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import ManualTriggerSensorEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COMMAND_TIMEOUT,
    CONF_JSON_ATTRIBUTES,
    CONF_JSON_ATTRIBUTES_PATH,
    LOGGER,
    TRIGGER_ENTITY_OPTIONS,
)
from .utils import async_check_output_or_log

DEFAULT_NAME = "Command Sensor"

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Command Sensor."""
    if not discovery_info:
        return

    discovery_info = cast(DiscoveryInfoType, discovery_info)
    sensor_config = discovery_info

    command: str = sensor_config[CONF_COMMAND]
    command_timeout: int = sensor_config[CONF_COMMAND_TIMEOUT]
    json_attributes: list[str] | None = sensor_config.get(CONF_JSON_ATTRIBUTES)
    json_attributes_path: str | None = sensor_config.get(CONF_JSON_ATTRIBUTES_PATH)
    scan_interval: timedelta = sensor_config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    value_template: Template | None = sensor_config.get(CONF_VALUE_TEMPLATE)
    data = CommandSensorData(hass, command, command_timeout)

    trigger_entity_config = {
        CONF_NAME: Template(sensor_config[CONF_NAME], hass),
        **{k: v for k, v in sensor_config.items() if k in TRIGGER_ENTITY_OPTIONS},
    }

    async_add_entities(
        [
            CommandSensor(
                data,
                trigger_entity_config,
                value_template,
                json_attributes,
                json_attributes_path,
                scan_interval,
            )
        ]
    )


class CommandSensor(ManualTriggerSensorEntity):
    """Representation of a sensor that is using shell commands."""

    _attr_should_poll = False

    def __init__(
        self,
        data: CommandSensorData,
        config: ConfigType,
        value_template: Template | None,
        json_attributes: list[str] | None,
        json_attributes_path: str | None,
        scan_interval: timedelta,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(self.hass, config)
        self.data = data
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._json_attributes = json_attributes
        self._json_attributes_path = json_attributes_path
        self._attr_native_value = None
        self._value_template = value_template
        self._scan_interval = scan_interval
        self._process_updates: asyncio.Lock | None = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return self._attr_extra_state_attributes

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self._update_entity_state()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._update_entity_state,
                self._scan_interval,
                name=f"Command Line Sensor - {self.name}",
                cancel_on_shutdown=True,
            ),
        )

    async def _update_entity_state(self, now: datetime | None = None) -> None:
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
        await self.data.async_update()
        value = self.data.value

        if self._json_attributes:
            self._attr_extra_state_attributes = {}
            if value:
                try:
                    json_dict = json.loads(value)
                    if self._json_attributes_path is not None:
                        json_dict = jsonpath(json_dict, self._json_attributes_path)
                    # jsonpath will always store the result in json_dict[0]
                    # so the next line happens to work exactly as needed to
                    # find the result
                    if isinstance(json_dict, list):
                        json_dict = json_dict[0]
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

        self._attr_native_value = None
        if self._value_template is not None and value is not None:
            value = self._value_template.async_render_with_possible_json_value(
                value,
                None,
            )

        if self.device_class not in {
            SensorDeviceClass.DATE,
            SensorDeviceClass.TIMESTAMP,
        }:
            self._attr_native_value = value
            self._process_manual_data(value)
            return

        if value is not None:
            self._attr_native_value = async_parse_date_datetime(
                value, self.entity_id, self.device_class
            )
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

    async def async_update(self) -> None:
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
                rendered_args = args_compiled.async_render(args_to_render)
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
        self.value = await async_check_output_or_log(command, self.timeout)
