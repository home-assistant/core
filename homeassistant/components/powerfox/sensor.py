"""Sensors flor for Powerfox integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from powerfox import Device, PowerMeter, WaterMeter

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PowerfoxConfigEntry
from .const import DOMAIN
from .coordinator import PowerfoxDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class PowerfoxPowerSensorEntityDescription(SensorEntityDescription):
    """Describes Poweropti power sensor entity."""

    value_fn: Callable[[PowerMeter], StateType]


SENSORS_POWER: tuple[PowerfoxPowerSensorEntityDescription, ...] = (
    PowerfoxPowerSensorEntityDescription(
        key="power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda meter: meter.power,
    ),
    PowerfoxPowerSensorEntityDescription(
        key="energy_usage",
        translation_key="energy_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_usage,
    ),
    PowerfoxPowerSensorEntityDescription(
        key="energy_usage_low_tariff",
        translation_key="energy_usage_low_tariff",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_usage_low_tariff,
    ),
    PowerfoxPowerSensorEntityDescription(
        key="energy_usage_high_tariff",
        translation_key="energy_usage_high_tariff",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_usage_high_tariff,
    ),
    PowerfoxPowerSensorEntityDescription(
        key="energy_return",
        translation_key="energy_return",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_return,
    ),
)


@dataclass(frozen=True, kw_only=True)
class PowerfoxWaterSensorEntityDescription(SensorEntityDescription):
    """Describes Poweropti water sensor entity."""

    value_fn: Callable[[WaterMeter], StateType]


SENSORS_WATER: tuple[PowerfoxWaterSensorEntityDescription, ...] = ()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerfoxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Powerfox sensors based on a config entry."""
    entities: list[SensorEntity] = []
    for coordinator in entry.runtime_data:
        if isinstance(coordinator.data, PowerMeter):
            entities.extend(
                PowerfoxPowerSensorEntity(
                    coordinator=coordinator,
                    description=description,
                    device=coordinator.device,
                )
                for description in SENSORS_POWER
            )
        if isinstance(coordinator.data, WaterMeter):
            entities.extend(
                PowerfoxWaterSensorEntity(
                    coordinator=coordinator,
                    description=description,
                    device=coordinator.device,
                )
                for description in SENSORS_WATER
            )
    async_add_entities(entities)


class PowerfoxPowerSensorEntity(
    CoordinatorEntity[PowerfoxDataUpdateCoordinator], SensorEntity
):
    """Defines a powerfox power meter sensor."""

    entity_description: PowerfoxPowerSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: PowerfoxDataUpdateCoordinator,
        device: Device,
        description: PowerfoxPowerSensorEntityDescription,
    ) -> None:
        """Initialize Powerfox power meter sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{device.device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            serial_number=device.device_id,
            manufacturer="Powerfox",
            name=device.name,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self.entity_description.value_fn(self.coordinator.data)


class PowerfoxWaterSensorEntity(
    CoordinatorEntity[PowerfoxDataUpdateCoordinator], SensorEntity
):
    """Defines a powerfox water meter sensor."""

    entity_description: PowerfoxWaterSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: PowerfoxDataUpdateCoordinator,
        device: Device,
        description: PowerfoxWaterSensorEntityDescription,
    ) -> None:
        """Initialize Powerfox water meter sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{device.device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            serial_number=device.device_id,
            manufacturer="Powerfox",
            name=device.name,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self.entity_description.value_fn(self.coordinator.data)
