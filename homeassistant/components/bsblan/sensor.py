"""Support for BSB-LAN sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BSBLanConfigEntry, BSBLanData
from .coordinator import BSBLanFastData
from .entity import BSBLanEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class BSBLanSensorEntityDescription(SensorEntityDescription):
    """Describes BSB-LAN sensor entity."""

    value_fn: Callable[[BSBLanFastData], StateType]
    exists_fn: Callable[[BSBLanFastData], bool] = lambda data: True


SENSOR_TYPES: tuple[BSBLanSensorEntityDescription, ...] = (
    BSBLanSensorEntityDescription(
        key="current_temperature",
        translation_key="current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.sensor.current_temperature.value
            if data.sensor.current_temperature is not None
            else None
        ),
        exists_fn=lambda data: data.sensor.current_temperature is not None,
    ),
    BSBLanSensorEntityDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.sensor.outside_temperature.value
            if data.sensor.outside_temperature is not None
            else None
        ),
        exists_fn=lambda data: data.sensor.outside_temperature is not None,
    ),
    BSBLanSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.sensor.total_energy.value
            if data.sensor.total_energy is not None
            else None
        ),
        exists_fn=lambda data: data.sensor.total_energy is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BSBLanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BSB-LAN sensor based on a config entry."""
    data = entry.runtime_data

    # Only create sensors for available data points
    entities = [
        BSBLanSensor(data, description)
        for description in SENSOR_TYPES
        if description.exists_fn(data.fast_coordinator.data)
    ]

    if entities:
        async_add_entities(entities)


class BSBLanSensor(BSBLanEntity, SensorEntity):
    """Defines a BSB-LAN sensor."""

    entity_description: BSBLanSensorEntityDescription

    def __init__(
        self,
        data: BSBLanData,
        description: BSBLanSensorEntityDescription,
    ) -> None:
        """Initialize BSB-LAN sensor."""
        super().__init__(data.fast_coordinator, data)
        self.entity_description = description
        self._attr_unique_id = f"{data.device.MAC}-{description.key}"
        self._attr_temperature_unit = data.fast_coordinator.client.get_temperature_unit

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
