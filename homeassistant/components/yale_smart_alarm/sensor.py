"""Sensors for Yale Alarm."""

from __future__ import annotations

from typing import cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import YaleConfigEntry
from .entity import YaleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YaleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yale sensor entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        YaleTemperatureSensor(coordinator, data)
        for data in coordinator.data["temp_sensors"]
    )


class YaleTemperatureSensor(YaleEntity, SensorEntity):
    """Representation of a Yale temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> StateType:
        "Return native value."
        return cast(float, self.coordinator.data["temp_map"][self._attr_unique_id])
