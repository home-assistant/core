"""Support for Autarco sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from autarco import Solar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AutarcoConfigEntry
from .const import DOMAIN
from .coordinator import AutarcoDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class AutarcoSolarSensorEntityDescription(SensorEntityDescription):
    """Describes an Autarco sensor entity."""

    state: Callable[[Solar], StateType]


SENSORS_SOLAR: tuple[AutarcoSolarSensorEntityDescription, ...] = (
    AutarcoSolarSensorEntityDescription(
        key="power_production",
        translation_key="power_production",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        state=lambda solar: solar.power_production,
    ),
    AutarcoSolarSensorEntityDescription(
        key="energy_production_today",
        translation_key="energy_production_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state=lambda solar: solar.energy_production_today,
    ),
    AutarcoSolarSensorEntityDescription(
        key="energy_production_month",
        translation_key="energy_production_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state=lambda solar: solar.energy_production_month,
    ),
    AutarcoSolarSensorEntityDescription(
        key="energy_production_total",
        translation_key="energy_production_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state=lambda solar: solar.energy_production_total,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutarcoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Autarco sensors based on a config entry."""
    for coordinator in entry.runtime_data:
        async_add_entities(
            AutarcoSolarSensorEntity(
                coordinator=coordinator,
                description=description,
            )
            for description in SENSORS_SOLAR
        )


class AutarcoSolarSensorEntity(
    CoordinatorEntity[AutarcoDataUpdateCoordinator], SensorEntity
):
    """Defines an Autarco solar sensor."""

    entity_description: AutarcoSolarSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: AutarcoDataUpdateCoordinator,
        description: AutarcoSolarSensorEntityDescription,
    ) -> None:
        """Initialize Autarco sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.site.site_id}_solar_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.site.site_id}_solar")},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Autarco",
            name="Solar",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.state(self.coordinator.data.solar)
