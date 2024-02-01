"""Allows to configure custom shell commands to turn a value for a sensor."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta
import json
from typing import Any, cast

from homeassistant.components.sensor import CONF_STATE_CLASS, SensorDeviceClass
from homeassistant.components.sensor.helpers import async_parse_date_datetime
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
    ManualTriggerSensorEntity,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import CONF_COMMAND_TIMEOUT, LOGGER
from .utils import check_output_or_log

CONF_JSON_ATTRIBUTES = "json_attributes"

DEFAULT_NAME = "Command Sensor"

TRIGGER_ENTITY_OPTIONS = (
    CONF_AVAILABILITY,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_PICTURE,
    CONF_UNIQUE_ID,
    CONF_STATE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Command Sensor."""

    discovery_info = cast(DiscoveryInfoType, discovery_info)
    sensor_config = discovery_info

    name: str = sensor_config[CONF_NAME]
    command: str = sensor_config[CONF_COMMAND]
    value_template: Template | None = sensor_config.get(CONF_VALUE_TEMPLATE)
    command_timeout: int = sensor_config[CONF_COMMAND_TIMEOUT]
    if value_template is not None:
        value_template.hass = hass
    json_attributes: list[str] | None = sensor_config.get(CONF_JSON_ATTRIBUTES)
    scan_interval: timedelta = sensor_config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    data = CommandSensorData(hass, command, command_timeout)

    trigger_entity_config = {CONF_NAME: Template(name, hass)}
    for key in TRIGGER_ENTITY_OPTIONS:
        if key not in sensor_config:
            continue
        trigger_entity_config[key] = sensor_config[key]

    async_add_entities(
        [
            CommandSensor(
                data,
                trigger_entity_config,
                value_template,
                json_attributes,
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
        scan_interval: timedelta,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(self.hass, config)
        self.data = data
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._json_attributes = json_attributes
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
