"""imports for sensor.py file."""

from collections.abc import Callable
from dataclasses import dataclass, field

from uhooapi import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
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
from .coordinator import UhooDataUpdateCoordinator

PARALLEL_UPDATES = True

DeviceValueFunction = Callable[[Device], float | None]


@dataclass(frozen=True)
class UhooSensorEntityDescription(SensorEntityDescription):
    """Extended SensorEntityDescription with a type-safe value function."""

    value_fn: DeviceValueFunction = field(default=lambda _: None)


SENSOR_TYPES: tuple[UhooSensorEntityDescription, ...] = (
    UhooSensorEntityDescription(
        key=API_CO,
        translation_key=API_CO,  # This will create "carbon_monoxide" in translations
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.as_dict["co"],
    ),
    UhooSensorEntityDescription(
        key=API_CO2,
        translation_key=API_CO2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.as_dict["co2"],
    ),
    UhooSensorEntityDescription(
        key=API_PM25,
        translation_key=API_PM25,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.as_dict["pm25"],
    ),
    UhooSensorEntityDescription(
        key=API_HUMIDITY,
        translation_key=API_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.as_dict["humidity"],
    ),
    UhooSensorEntityDescription(
        key=API_TEMP,
        translation_key=API_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # Base unit
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.as_dict["temperature"],
    ),
    UhooSensorEntityDescription(
        key=API_PRESSURE,
        translation_key=API_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.as_dict["air_pressure"],
    ),
    UhooSensorEntityDescription(
        key=API_TVOC,
        translation_key=API_TVOC,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.as_dict["tvoc"],
    ),
    UhooSensorEntityDescription(
        key=API_NO2,
        translation_key=API_NO2,
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.as_dict["no2"],
    ),
    UhooSensorEntityDescription(
        key=API_OZONE,
        translation_key=API_OZONE,
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.as_dict["ozone"],
    ),
    UhooSensorEntityDescription(
        key=API_VIRUS,
        translation_key=API_VIRUS,
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement="",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.as_dict["virus_index"],
    ),
    UhooSensorEntityDescription(
        key=API_MOLD,
        translation_key=API_MOLD,
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement="",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.as_dict["mold_index"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup sensor platform."""
    coordinator = config_entry.runtime_data
    sensors = [
        UhooSensorEntity(description, serial_number, coordinator)
        for serial_number in coordinator.data
        for description in SENSOR_TYPES
    ]

    async_add_entities(sensors, False)


class UhooSensorEntity(CoordinatorEntity[UhooDataUpdateCoordinator], SensorEntity):
    """Uhoo Sensor Object with init and methods."""

    entity_description: UhooSensorEntityDescription
    coordinator: UhooDataUpdateCoordinator
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

    @property
    def device(self) -> Device | None:
        """Return the device object for this sensor's serial number."""
        return self.coordinator.data.get(self._serial_number)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False

        if self._serial_number not in self.coordinator.data:
            return False

        device = self.device
        if device is None:
            return False

        return self.entity_description.value_fn(device) is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return DeviceInfo."""
        if (device := self.device) is None:
            return DeviceInfo(
                identifiers={(DOMAIN, self._serial_number)},
                name=f"uhoo {self._serial_number}",
                manufacturer=MANUFACTURER,
            )
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            name=device.device_name,
            model=MODEL,
            manufacturer=MANUFACTURER,
        )

    @property
    def native_value(self) -> StateType:
        """State of the sensor."""
        if (device := self.device) is None:
            return None
        value = self.entity_description.value_fn(device)
        if value is not None and self.entity_description.key == API_TEMP:
            if self.coordinator.user_settings_temp == "f":
                value = (value * 9 / 5) + 32
        return value
