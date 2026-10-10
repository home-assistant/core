"""Sensor platform for Meross Bluetooth."""

from dataclasses import dataclass
from typing import override

from meross_ble import MerossModel

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfDensity,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MerossBLEDataUpdateCoordinator, MerossConfigEntry
from .entity import MerossBLEEntity

PARALLEL_UPDATES = 0

SENSORS_BY_MODEL: dict[MerossModel, tuple[str, ...]] = {
    MerossModel.MS120: (
        "battery",
        "temperature",
        "humidity",
        "dew_point",
        "absolute_humidity",
        "vpd",
    ),
    MerossModel.MS220: ("battery",),
    MerossModel.MS420: ("battery",),
    MerossModel.MS700: (
        "battery",
        "temperature",
        "humidity",
        "dew_point",
        "absolute_humidity",
        "vpd",
    ),
}


@dataclass(frozen=True, kw_only=True)
class MerossBLESensorEntityDescription(SensorEntityDescription):
    """Sensor description."""


SENSOR_TYPES: dict[str, MerossBLESensorEntityDescription] = {
    "battery": MerossBLESensorEntityDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "temperature": MerossBLESensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": MerossBLESensorEntityDescription(
        key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "dew_point": MerossBLESensorEntityDescription(
        key="dew_point",
        translation_key="dew_point",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "absolute_humidity": MerossBLESensorEntityDescription(
        key="absolute_humidity",
        native_unit_of_measurement=UnitOfDensity.GRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.ABSOLUTE_HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "vpd": MerossBLESensorEntityDescription(
        key="vpd",
        translation_key="vpd",
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MerossConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meross BLE sensors from a config entry."""
    coordinator = entry.runtime_data
    keys = SENSORS_BY_MODEL.get(coordinator.model, ("battery",))
    async_add_entities(
        MerossBLESensor(coordinator, key) for key in keys if key in SENSOR_TYPES
    )


class MerossBLESensor(MerossBLEEntity, SensorEntity):
    """Meross BLE sensor."""

    entity_description: MerossBLESensorEntityDescription

    def __init__(
        self, coordinator: MerossBLEDataUpdateCoordinator, sensor: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = SENSOR_TYPES[sensor]
        self._sensor = sensor
        self._attr_unique_id = f"{coordinator.base_unique_id}-{sensor}"

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        return self.parsed_data.get(self._sensor)
