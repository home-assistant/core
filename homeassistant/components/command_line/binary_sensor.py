"""Support for custom shell commands to retrieve values."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    ManualTriggerEntity,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import CONF_COMMAND_TIMEOUT, LOGGER
from .sensor import CommandSensorData

DEFAULT_NAME = "Binary Command Sensor"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Command line Binary Sensor."""

    discovery_info = cast(DiscoveryInfoType, discovery_info)
    binary_sensor_config = discovery_info

    name: str = binary_sensor_config.get(CONF_NAME, DEFAULT_NAME)
    command: str = binary_sensor_config[CONF_COMMAND]
    payload_off: str = binary_sensor_config[CONF_PAYLOAD_OFF]
    payload_on: str = binary_sensor_config[CONF_PAYLOAD_ON]
    device_class: BinarySensorDeviceClass | None = binary_sensor_config.get(
        CONF_DEVICE_CLASS
    )
    icon: Template | None = binary_sensor_config.get(CONF_ICON)
    value_template: Template | None = binary_sensor_config.get(CONF_VALUE_TEMPLATE)
    command_timeout: int = binary_sensor_config[CONF_COMMAND_TIMEOUT]
    unique_id: str | None = binary_sensor_config.get(CONF_UNIQUE_ID)
    scan_interval: timedelta = binary_sensor_config.get(
        CONF_SCAN_INTERVAL, SCAN_INTERVAL
    )
    availability: Template | None = binary_sensor_config.get(CONF_AVAILABILITY)
    if value_template is not None:
        value_template.hass = hass
    data = CommandSensorData(hass, command, command_timeout)

    trigger_entity_config = {
        CONF_UNIQUE_ID: unique_id,
        CONF_NAME: Template(name, hass),
        CONF_DEVICE_CLASS: device_class,
        CONF_ICON: icon,
        CONF_AVAILABILITY: availability,
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
        await self._update_entity_state()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._update_entity_state,
                self._scan_interval,
                name=f"Command Line Binary Sensor - {self.name}",
                cancel_on_shutdown=True,
            ),
        )

    async def _update_entity_state(self, now: datetime | None = None) -> None:
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
