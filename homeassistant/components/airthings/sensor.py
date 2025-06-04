"""Support for Airthings sensors."""

from __future__ import annotations

from airthings import AirthingsDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirthingsConfigEntry, AirthingsDataCoordinatorType
from .const import DOMAIN

SENSORS: dict[str, SensorEntityDescription] = {
    "radonShortTermAvg": SensorEntityDescription(
        key="radonShortTermAvg",
        native_unit_of_measurement="Bq/m³",
        translation_key="radon",
    ),
    "temp": SensorEntityDescription(
        key="temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pressure": SensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "co2": SensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "voc": SensorEntityDescription(
        key="voc",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "light": SensorEntityDescription(
        key="light",
        native_unit_of_measurement=PERCENTAGE,
        translation_key="light",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "lux": SensorEntityDescription(
        key="lux",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "virusRisk": SensorEntityDescription(
        key="virusRisk",
        translation_key="virus_risk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "mold": SensorEntityDescription(
        key="mold",
        translation_key="mold",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "rssi": SensorEntityDescription(
        key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pm1": SensorEntityDescription(
        key="pm1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pm25": SensorEntityDescription(
        key="pm25",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirthingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Airthings sensor."""

    coordinator = entry.runtime_data
    entities = [
        AirthingsHeaterEnergySensor(
            coordinator,
            airthings_device,
            SENSORS[sensor_types],
        )
        for airthings_device in coordinator.data.values()
        for sensor_types in airthings_device.sensor_types
        if sensor_types in SENSORS
    ]
    async_add_entities(entities)


class AirthingsHeaterEnergySensor(
    CoordinatorEntity[AirthingsDataCoordinatorType], SensorEntity
):
    """Representation of a Airthings Sensor device."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirthingsDataCoordinatorType,
        airthings_device: AirthingsDevice,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description

        self._attr_unique_id = f"{airthings_device.device_id}_{entity_description.key}"
        self._id = airthings_device.device_id
        self._attr_device_info = DeviceInfo(
            configuration_url=(
                f"https://dashboard.airthings.com/devices/{airthings_device.device_id}"
            ),
            identifiers={(DOMAIN, airthings_device.device_id)},
            name=airthings_device.name,
            manufacturer="Airthings",
            model=airthings_device.product_name,
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data[self._id].sensors[self.entity_description.key]  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        """Check if device and sensor is available in data."""
        return (
            super().available
            and self.entity_description.key in self.coordinator.data[self._id].sensors
        )
