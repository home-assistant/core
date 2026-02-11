"""Support for Epion API."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EpionConfigEntry, EpionCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        key="co2",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        key="temperature",
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        key="humidity",
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
        key="pressure",
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EpionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add an Epion entry."""
    coordinator = entry.runtime_data

    entities = [
        EpionSensor(coordinator, epion_device_id, description)
        for epion_device_id in coordinator.data
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class EpionSensor(CoordinatorEntity[EpionCoordinator], SensorEntity):
    """Representation of an Epion Air sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EpionCoordinator,
        epion_device_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize an EpionSensor."""
        super().__init__(coordinator)
        self._epion_device_id = epion_device_id
        self.entity_description = description
        self._attr_unique_id = f"{epion_device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, epion_device_id)},
            manufacturer="Epion",
            name=self.device.get("deviceName"),
            sw_version=self.device.get("fwVersion"),
            model="Epion Air",
        )

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the sensor, or None if the relevant sensor can't produce a current measurement."""
        return self.device.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Return the availability of the device that provides this sensor data."""
        return super().available and self._epion_device_id in self.coordinator.data

    @property
    def device(self) -> dict[str, Any]:
        """Get the device record from the current coordinator data, or None if there is no data being returned for this device ID anymore."""
        return self.coordinator.data[self._epion_device_id]
