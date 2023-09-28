"""Support for custom shell commands to retrieve values."""
from __future__ import annotations

import asyncio
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import ManualTriggerEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN, LOGGER
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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Command line Binary Sensor."""

    if binary_sensor_config := config:
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_binary_sensor",
            breaks_in_ha_version="2023.12.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_platform_yaml",
            translation_placeholders={"platform": BINARY_SENSOR_DOMAIN},
        )
    if discovery_info:
        binary_sensor_config = discovery_info

    name: str = binary_sensor_config.get(CONF_NAME, DEFAULT_NAME)
    command: str = binary_sensor_config[CONF_COMMAND]
    payload_off: str = binary_sensor_config[CONF_PAYLOAD_OFF]
    payload_on: str = binary_sensor_config[CONF_PAYLOAD_ON]
    device_class: BinarySensorDeviceClass | None = binary_sensor_config.get(
        CONF_DEVICE_CLASS
    )
    value_template: Template | None = binary_sensor_config.get(CONF_VALUE_TEMPLATE)
    command_timeout: int = binary_sensor_config[CONF_COMMAND_TIMEOUT]
    unique_id: str | None = binary_sensor_config.get(CONF_UNIQUE_ID)
    scan_interval: timedelta = binary_sensor_config.get(
        CONF_SCAN_INTERVAL, SCAN_INTERVAL
    )
    if value_template is not None:
        value_template.hass = hass
    data = CommandSensorData(hass, command, command_timeout)

    trigger_entity_config = {
        CONF_UNIQUE_ID: unique_id,
        CONF_NAME: Template(name, hass),
        CONF_DEVICE_CLASS: device_class,
    }

    async_add_entities(
        [
            CommandBinarySensor(
                data,
                trigger_entity_config,
                payload_on,
                payload_off,
                value_template,
                scan_interval,
            )
        ],
    )


class CommandBinarySensor(ManualTriggerEntity, BinarySensorEntity):
    """Representation of a command line binary sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        data: CommandSensorData,
        config: ConfigType,
        payload_on: str,
        payload_off: str,
        value_template: Template | None,
        scan_interval: timedelta,
    ) -> None:
        """Initialize the Command line binary sensor."""
        super().__init__(self.hass, config)
        self.data = data
        self._attr_is_on = None
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._value_template = value_template
        self._scan_interval = scan_interval
        self._process_updates: asyncio.Lock | None = None

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self._update_entity_state(None)
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._update_entity_state,
                self._scan_interval,
                name=f"Command Line Binary Sensor - {self.name}",
                cancel_on_shutdown=True,
            ),
        )

    async def _update_entity_state(self, now) -> None:
        """Update the state of the entity."""
        if self._process_updates is None:
            self._process_updates = asyncio.Lock()
        if self._process_updates.locked():
            LOGGER.warning(
                "Updating Command Line Binary Sensor %s took longer than the scheduled update interval %s",
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

        if self._value_template is not None:
            value = self._value_template.async_render_with_possible_json_value(
                value, None
            )
        self._attr_is_on = None
        if value == self._payload_on:
            self._attr_is_on = True
        elif value == self._payload_off:
            self._attr_is_on = False

        self._process_manual_data(value)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._update_entity_state(dt_util.now())
