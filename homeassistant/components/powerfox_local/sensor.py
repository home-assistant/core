"""Sensors for Powerfox Local integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from powerfox import LocalResponse

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PowerfoxLocalConfigEntry, PowerfoxLocalDataUpdateCoordinator
from .entity import PowerfoxLocalEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PowerfoxLocalSensorEntityDescription(SensorEntityDescription):
    """Describes Powerfox Local sensor entity."""

    value_fn: Callable[[LocalResponse], float | int | None]


SENSORS: tuple[PowerfoxLocalSensorEntityDescription, ...] = (
    PowerfoxLocalSensorEntityDescription(
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power,
    ),
    PowerfoxLocalSensorEntityDescription(
        key="energy_usage",
        translation_key="energy_usage",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.energy_usage,
    ),
    PowerfoxLocalSensorEntityDescription(
        key="energy_usage_high_tariff",
        translation_key="energy_usage_high_tariff",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.energy_usage_high_tariff,
    ),
    PowerfoxLocalSensorEntityDescription(
        key="energy_usage_low_tariff",
        translation_key="energy_usage_low_tariff",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.energy_usage_low_tariff,
    ),
    PowerfoxLocalSensorEntityDescription(
        key="energy_return",
        translation_key="energy_return",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.energy_return,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerfoxLocalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Powerfox Local sensors based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        PowerfoxLocalSensorEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in SENSORS
        if description.value_fn(coordinator.data) is not None
    )


class PowerfoxLocalSensorEntity(PowerfoxLocalEntity, SensorEntity):
    """Defines a Powerfox Local sensor."""

    entity_description: PowerfoxLocalSensorEntityDescription

    def __init__(
        self,
        coordinator: PowerfoxLocalDataUpdateCoordinator,
        description: PowerfoxLocalSensorEntityDescription,
    ) -> None:
        """Initialize the Powerfox Local sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the entity."""
        return self.entity_description.value_fn(self.coordinator.data)
