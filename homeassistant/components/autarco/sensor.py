"""Support for Autarco sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AutarcoData, AutarcoDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class AutarcoSensorEntityDescription(SensorEntityDescription):
    """Describes an Autarco sensor entity."""

    state: Callable[[AutarcoData], Any | None]


SENSORS_SOLAR: tuple[AutarcoSensorEntityDescription, ...] = (
    AutarcoSensorEntityDescription(
        key="power_production",
        translation_key="power_production",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        state=lambda data: data.solar.power_production,
    ),
    AutarcoSensorEntityDescription(
        key="energy_production_today",
        translation_key="energy_production_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state=lambda data: data.solar.energy_production_today,
    ),
    AutarcoSensorEntityDescription(
        key="energy_production_month",
        translation_key="energy_production_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state=lambda data: data.solar.energy_production_month,
    ),
    AutarcoSensorEntityDescription(
        key="energy_production_total",
        translation_key="energy_production_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state=lambda data: data.solar.energy_production_total,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Autarco sensors based on a config entry."""
    coordinator: AutarcoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[AutarcoSensorEntity] = [
        AutarcoSensorEntity(
            coordinator=coordinator,
            description=description,
            name="Solar",
            service="solar",
        )
        for description in SENSORS_SOLAR
    ]
    async_add_entities(entities)


class AutarcoSensorEntity(
    CoordinatorEntity[AutarcoDataUpdateCoordinator], SensorEntity
):
    """Defines an Autarco sensor."""

    coordinator: AutarcoDataUpdateCoordinator
    entity_description: AutarcoSensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: AutarcoDataUpdateCoordinator,
        description: AutarcoSensorEntityDescription,
        name: str,
        service: str,
    ) -> None:
        """Initialize Autarco sensor."""
        super().__init__(coordinator=coordinator)

        self.entity_description = description
        self.entity_id = f"{SENSOR_DOMAIN}.{service}_{description.key}"
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{service}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_{service}")},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Autarco",
            name=name,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.state(self.coordinator.data)
