"""Custom uhoo sensors setup."""

from collections.abc import Callable
from dataclasses import dataclass

from uhooapi import Device

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
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    API_CO,
    API_CO2,
    API_HUMIDITY,
    API_MOLD,
    API_NO2,
    API_OZONE,
    API_PM25,
    API_PRESSURE,
    API_TEMP,
    API_TVOC,
    API_VIRUS,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .coordinator import UhooConfigEntry, UhooDataUpdateCoordinator

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class UhooSensorEntityDescription(SensorEntityDescription):
    """Extended SensorEntityDescription with a type-safe value function."""

    value_fn: Callable[[Device], float | None]


SENSOR_TYPES: tuple[UhooSensorEntityDescription, ...] = (
    UhooSensorEntityDescription(
        key=API_CO,
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.co,
    ),
    UhooSensorEntityDescription(
        key=API_CO2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.co2,
    ),
    UhooSensorEntityDescription(
        key=API_PM25,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.pm25,
    ),
    UhooSensorEntityDescription(
        key=API_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.humidity,
    ),
    UhooSensorEntityDescription(
        key=API_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # Base unit
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature,
    ),
    UhooSensorEntityDescription(
        key=API_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.air_pressure,
    ),
    UhooSensorEntityDescription(
        key=API_TVOC,
        translation_key="volatile_organic_compounds",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tvoc,
    ),
    UhooSensorEntityDescription(
        key=API_NO2,
        translation_key="nitrogen_dioxide",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.no2,
    ),
    UhooSensorEntityDescription(
        key=API_OZONE,
        translation_key="ozone",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.ozone,
    ),
    UhooSensorEntityDescription(
        key=API_VIRUS,
        translation_key=API_VIRUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.virus_index,
    ),
    UhooSensorEntityDescription(
        key=API_MOLD,
        translation_key=API_MOLD,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.mold_index,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UhooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup sensor platform."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        UhooSensorEntity(description, serial_number, coordinator)
        for serial_number in coordinator.data
        for description in SENSOR_TYPES
    )


class UhooSensorEntity(CoordinatorEntity[UhooDataUpdateCoordinator], SensorEntity):
    """Uhoo Sensor Object with init and methods."""

    entity_description: UhooSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        description: UhooSensorEntityDescription,
        serial_number: str,
        coordinator: UhooDataUpdateCoordinator,
    ) -> None:
        """Initialize Uhoo Sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=self.device.device_name,
            model=MODEL,
            manufacturer=MANUFACTURER,
            serial_number=serial_number,
        )

    @property
    def device(self) -> Device:
        """Return the device object for this sensor's serial number."""
        return self.coordinator.data[self._serial_number]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._serial_number in self.coordinator.data

    @property
    def native_value(self) -> StateType:
        """State of the sensor."""
        return self.entity_description.value_fn(self.device)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement."""
        if self.entity_description.key == API_TEMP:
            if self.device.user_settings["temp"] == "f":
                return UnitOfTemperature.FAHRENHEIT
            return UnitOfTemperature.CELSIUS
        return super().native_unit_of_measurement
