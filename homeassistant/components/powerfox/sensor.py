"""Sensors for Powerfox integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from powerfox import Device, HeatMeter, PowerMeter, WaterMeter

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PowerfoxConfigEntry, PowerfoxDataUpdateCoordinator
from .entity import PowerfoxEntity


@dataclass(frozen=True, kw_only=True)
class PowerfoxSensorEntityDescription[T: (PowerMeter, WaterMeter, HeatMeter)](
    SensorEntityDescription
):
    """Describes Poweropti sensor entity."""

    value_fn: Callable[[T], float | int | None]


SENSORS_POWER: tuple[PowerfoxSensorEntityDescription[PowerMeter], ...] = (
    PowerfoxSensorEntityDescription[PowerMeter](
        key="power",
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
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_usage_low_tariff,
    ),
    PowerfoxSensorEntityDescription[PowerMeter](
        key="energy_usage_high_tariff",
        translation_key="energy_usage_high_tariff",
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


SENSORS_WATER: tuple[PowerfoxSensorEntityDescription[WaterMeter], ...] = (
    PowerfoxSensorEntityDescription[WaterMeter](
        key="cold_water",
        translation_key="cold_water",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.cold_water,
    ),
    PowerfoxSensorEntityDescription[WaterMeter](
        key="warm_water",
        translation_key="warm_water",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.warm_water,
    ),
)

SENSORS_HEAT: tuple[PowerfoxSensorEntityDescription[HeatMeter], ...] = (
    PowerfoxSensorEntityDescription[HeatMeter](
        key="heat_total_energy",
        translation_key="heat_total_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.total_energy,
    ),
    PowerfoxSensorEntityDescription[HeatMeter](
        key="heat_delta_energy",
        translation_key="heat_delta_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda meter: meter.delta_energy,
    ),
    PowerfoxSensorEntityDescription[HeatMeter](
        key="heat_total_volume",
        translation_key="heat_total_volume",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.total_volume,
    ),
    PowerfoxSensorEntityDescription[HeatMeter](
        key="heat_delta_volume",
        translation_key="heat_delta_volume",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        value_fn=lambda meter: meter.delta_volume,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerfoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
                if description.value_fn(coordinator.data) is not None
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
        if isinstance(coordinator.data, HeatMeter):
            entities.extend(
                PowerfoxSensorEntity(
                    coordinator=coordinator,
                    description=description,
                    device=coordinator.device,
                )
                for description in SENSORS_HEAT
            )
    async_add_entities(entities)


class PowerfoxSensorEntity(PowerfoxEntity, SensorEntity):
    """Defines a powerfox power meter sensor."""

    entity_description: PowerfoxSensorEntityDescription

    def __init__(
        self,
        coordinator: PowerfoxDataUpdateCoordinator,
        device: Device,
        description: PowerfoxSensorEntityDescription,
    ) -> None:
        """Initialize Powerfox power meter sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.id}_{description.key}"

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the entity."""
        return self.entity_description.value_fn(self.coordinator.data)
