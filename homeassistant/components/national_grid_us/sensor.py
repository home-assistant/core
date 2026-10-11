"""Sensor platform for the National Grid US integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import (
    MeterData,
    NationalGridConfigEntry,
    NationalGridDataUpdateCoordinator,
)
from .entity import NationalGridEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NationalGridSensorEntityDescription(SensorEntityDescription):
    """Describe a National Grid sensor entity."""

    value_fn: Callable[[MeterData], float | None]
    unit_fn: Callable[[MeterData], str] | None = None
    device_class_fn: Callable[[MeterData], SensorDeviceClass] | None = None


def _get_energy_unit(meter_data: MeterData) -> str:
    """Get the appropriate energy unit based on fuel type."""
    if meter_data.meter["fuelType"].upper() == "GAS":
        return UnitOfVolume.CENTUM_CUBIC_FEET
    return UnitOfEnergy.KILO_WATT_HOUR


def _get_energy_device_class(meter_data: MeterData) -> SensorDeviceClass:
    """Get the device class based on fuel type."""
    if meter_data.meter["fuelType"].upper() == "GAS":
        return SensorDeviceClass.GAS
    return SensorDeviceClass.ENERGY


SENSOR_DESCRIPTIONS: tuple[NationalGridSensorEntityDescription, ...] = (
    NationalGridSensorEntityDescription(
        key="energy_usage",
        translation_key="energy_usage",
        value_fn=lambda m: m.latest_usage,
        unit_fn=_get_energy_unit,
        device_class_fn=_get_energy_device_class,
    ),
    NationalGridSensorEntityDescription(
        key="energy_cost",
        translation_key="energy_cost",
        native_unit_of_measurement="USD",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda m: m.latest_cost,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NationalGridConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data

    entities: list[NationalGridSensor] = []

    for meter_key, meter_data in coordinator.data.meters.items():
        entities.extend(
            NationalGridSensor(
                coordinator=coordinator,
                meter_key=meter_key,
                entity_description=description,
                meter_data=meter_data,
            )
            for description in SENSOR_DESCRIPTIONS
        )

    async_add_entities(entities)


class NationalGridSensor(NationalGridEntity, SensorEntity):
    """National Grid sensor entity."""

    entity_description: NationalGridSensorEntityDescription

    def __init__(
        self,
        coordinator: NationalGridDataUpdateCoordinator,
        meter_key: str,
        entity_description: NationalGridSensorEntityDescription,
        meter_data: MeterData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, meter_key)
        self.entity_description = entity_description
        self._attr_unique_id = f"{meter_key}_{entity_description.key}"
        if entity_description.unit_fn:
            self._attr_native_unit_of_measurement = entity_description.unit_fn(
                meter_data
            )
        if entity_description.device_class_fn:
            self._attr_device_class = entity_description.device_class_fn(meter_data)

    @property
    @override
    def available(self) -> bool:
        """Return if the sensor is available."""
        return (
            super().available
            and self.coordinator.data.meters.get(self._meter_key) is not None
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        meter_data = self.coordinator.data.meters[self._meter_key]
        return self.entity_description.value_fn(meter_data)
