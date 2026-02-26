"""Sensor platform for NuHeat integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import NuHeatEnergyData
from .const import DOMAIN, MANUFACTURER

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NuHeatSensorEntityDescription(SensorEntityDescription):
    """Describes NuHeat sensor entity."""

    value_fn: Callable[[NuHeatEnergyData], StateType]


SENSOR_DESCRIPTIONS: tuple[NuHeatSensorEntityDescription, ...] = (
    NuHeatSensorEntityDescription(
        key="energy",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda data: data.energy_kwh,
    ),
    NuHeatSensorEntityDescription(
        key="heating_time",
        translation_key="heating_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: data.heating_minutes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NuHeat sensor entities."""
    thermostat, _coordinator, energy_coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[NuHeatSensor] = []

    for description in SENSOR_DESCRIPTIONS:
        # Only add energy sensor if we have valid kWh data
        if description.key == "energy" and energy_coordinator.data.energy_kwh is None:
            continue

        entities.append(
            NuHeatSensor(
                energy_coordinator,
                thermostat,
                description,
            )
        )

    async_add_entities(entities)


class NuHeatSensor(
    CoordinatorEntity[DataUpdateCoordinator[NuHeatEnergyData]], SensorEntity
):
    """NuHeat sensor entity."""

    _attr_has_entity_name = True
    entity_description: NuHeatSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NuHeatEnergyData],
        thermostat: Any,
        description: NuHeatSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._thermostat = thermostat
        self.entity_description = description
        self._attr_unique_id = f"{thermostat.serial_number}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if self.entity_description.key == "energy":
            return self.coordinator.data.energy_kwh is not None
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._thermostat.serial_number)},
            serial_number=self._thermostat.serial_number,
            name=self._thermostat.room,
            model="nVent Signature",
            manufacturer=MANUFACTURER,
            suggested_area=self._thermostat.room,
        )
