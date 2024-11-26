"""Sensors for Powerfox integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic

from powerfox import Device, PowerMeter, WaterMeter

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PowerfoxConfigEntry
from .coordinator import PowerfoxDataUpdateCoordinator, T
from .entity import PowerfoxEntity


@dataclass(frozen=True, kw_only=True)
class PowerfoxSensorEntityDescription(Generic[T], SensorEntityDescription):
    """Describes Poweropti sensor entity."""

    value_fn: Callable[[T], StateType]


SENSORS_POWER: tuple[PowerfoxSensorEntityDescription, ...] = (
    PowerfoxSensorEntityDescription[PowerMeter](
        key="power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda meter: meter.power,
    ),
    PowerfoxSensorEntityDescription[PowerMeter](
        key="energy_usage",
        translation_key="energy_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_usage,
    ),
    PowerfoxSensorEntityDescription[PowerMeter](
        key="energy_usage_low_tariff",
        translation_key="energy_usage_low_tariff",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_usage_low_tariff,
    ),
    PowerfoxSensorEntityDescription[PowerMeter](
        key="energy_usage_high_tariff",
        translation_key="energy_usage_high_tariff",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_usage_high_tariff,
    ),
    PowerfoxSensorEntityDescription[PowerMeter](
        key="energy_return",
        translation_key="energy_return",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_return,
    ),
)


SENSORS_WATER: tuple[PowerfoxSensorEntityDescription, ...] = ()


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
                PowerfoxSensorEntity(
                    coordinator=coordinator,
                    description=description,
                    device=coordinator.device,
                )
                for description in SENSORS_POWER
            )
        if isinstance(coordinator.data, WaterMeter):
            entities.extend(
                PowerfoxSensorEntity(
                    coordinator=coordinator,
                    description=description,
                    device=coordinator.device,
                )
                for description in SENSORS_WATER
            )
    async_add_entities(entities)


class PowerfoxSensorEntity(PowerfoxEntity, SensorEntity):
    """Defines a powerfox power meter sensor."""

    entity_description: PowerfoxSensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: PowerfoxDataUpdateCoordinator,
        device: Device,
        description: PowerfoxSensorEntityDescription,
    ) -> None:
        """Initialize Powerfox power meter sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self.entity_description.value_fn(self.coordinator.data)
