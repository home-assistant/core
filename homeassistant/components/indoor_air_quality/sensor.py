"""Sensor platform for the Indoor Air Quality integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndoorAirQualityConfigEntry, IndoorAirQualityController
from .const import DOMAIN, LEVELS, NAME, SENSOR_INDEX, SENSOR_LEVEL, SENSOR_TYPES

_LOGGER: Final = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


def _device_info_from_device_id(
    hass: HomeAssistant, device_id: str | None
) -> DeviceInfo | None:
    """Return DeviceInfo linking to a parent device, when configured."""
    if not device_id:
        return None
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        return None
    if device.identifiers:
        return DeviceInfo(identifiers=device.identifiers)
    if device.connections:
        return DeviceInfo(connections=device.connections)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndoorAirQualityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Indoor Air Quality sensors from a config entry."""
    controller = entry.runtime_data
    device_id = entry.data.get(CONF_DEVICE_ID)
    parent_device = _device_info_from_device_id(hass, device_id)

    async_add_entities(
        IndoorAirQualitySensor(controller, sensor_type, parent_device)
        for sensor_type in SENSOR_TYPES
    )


class IndoorAirQualitySensor(SensorEntity):
    """Indoor Air Quality sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        controller: IndoorAirQualityController,
        sensor_type: str,
        parent_device: DeviceInfo | None,
    ) -> None:
        """Initialize the sensor."""
        self._controller = controller
        self._sensor_type = sensor_type
        self._attr_translation_key = sensor_type
        self._attr_unique_id = f"{controller.unique_id}_{sensor_type}"

        if sensor_type == SENSOR_LEVEL:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(LEVELS)
        elif sensor_type == SENSOR_INDEX:
            self._attr_state_class = SensorStateClass.MEASUREMENT

        if parent_device is not None:
            self._attr_device_info = parent_device
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, controller.unique_id)},
                manufacturer=NAME,
                name=controller.name,
                entry_type=dr.DeviceEntryType.SERVICE,
            )

    @property
    def native_value(self) -> int | str | None:
        """Return the sensor's current value."""
        if self._sensor_type == SENSOR_INDEX:
            return self._controller.iaq_index
        if self._sensor_type == SENSOR_LEVEL:
            return self._controller.iaq_level
        return None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return controller-wide diagnostic attributes."""
        return self._controller.extra_state_attributes

    async def async_added_to_hass(self) -> None:
        """Subscribe to controller updates."""

        @callback
        def _async_handle_update() -> None:
            self.async_write_ha_state()

        self.async_on_remove(self._controller.async_add_listener(_async_handle_update))
