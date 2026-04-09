"""Sensor platform for Xthings Cloud."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import XthingsCloudCoordinator
from .entity import XthingsCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator: XthingsCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for device_id, device_data in coordinator.data.items():
        if device_data.get("type") == "lock":
            entities.append(
                XthingsCloudBatterySensor(coordinator, device_id, device_data)
            )
    async_add_entities(entities)


class XthingsCloudBatterySensor(XthingsCloudEntity, SensorEntity):
    """Xthings Cloud battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_name = "Battery"

    def __init__(
        self,
        coordinator: XthingsCloudCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_battery"

    @property
    def native_value(self) -> int | None:
        return self.device_data.get("status", {}).get("battery")
