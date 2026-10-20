"""Sensor mapping from library device state."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from sensecap_lorawan import (
    S2101,
    S2102,
    S2103,
    S2104,
    S2105,
    S2106,
    S2107,
    S2120,
    SenseCapDevice,
)

from homeassistant.components.lorawan import LoRaWANEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfConductivity,
    UnitOfLength,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SenseCapConfigEntry
from .coordinator import SenseCapCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SenseCapSensorDescription[DeviceT: SenseCapDevice](SensorEntityDescription):
    """Select a typed measurement from the device model."""

    device_types: tuple[type[DeviceT], ...]
    value_fn: Callable[[DeviceT], float | None]


DESCRIPTIONS: tuple[SenseCapSensorDescription[Any], ...] = (
    SenseCapSensorDescription[S2101 | S2103 | S2106 | S2120](
        key="temperature",
        device_types=(S2101, S2103, S2106, S2120),
        value_fn=lambda device: device.temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2101 | S2103 | S2120](
        key="humidity",
        device_types=(S2101, S2103, S2120),
        value_fn=lambda device: device.humidity,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2102 | S2120](
        key="illuminance",
        device_types=(S2102, S2120),
        value_fn=lambda device: device.illuminance,
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2103](
        key="carbon_dioxide",
        device_types=(S2103,),
        value_fn=lambda device: device.co2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2104](
        key="soil_temperature",
        device_types=(S2104,),
        value_fn=lambda device: device.soil_temperature,
        translation_key="soil_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2104](
        key="soil_moisture",
        device_types=(S2104,),
        value_fn=lambda device: device.soil_moisture,
        translation_key="soil_moisture",
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2105](
        key="conductivity",
        device_types=(S2105,),
        value_fn=lambda device: device.conductivity,
        device_class=SensorDeviceClass.CONDUCTIVITY,
        native_unit_of_measurement=UnitOfConductivity.MILLISIEMENS_PER_CM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2106](
        key="ph",
        device_types=(S2106,),
        value_fn=lambda device: device.ph,
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2120](
        key="pressure",
        device_types=(S2120,),
        value_fn=lambda device: device.pressure,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PA,
        suggested_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2120](
        key="uv_index",
        device_types=(S2120,),
        value_fn=lambda device: device.uv_index,
        translation_key="uv_index",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2120](
        key="wind_speed",
        device_types=(S2120,),
        value_fn=lambda device: device.wind_speed,
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2120](
        key="wind_direction",
        device_types=(S2120,),
        value_fn=lambda device: device.wind_direction,
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
    ),
    SenseCapSensorDescription[S2120](
        key="wind_gust",
        device_types=(S2120,),
        value_fn=lambda device: device.wind_gust,
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2120](
        key="rainfall",
        device_types=(S2120,),
        value_fn=lambda device: device.rainfall,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2120](
        key="rain_accumulation",
        device_types=(S2120,),
        value_fn=lambda device: device.rain_accumulation,
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SenseCapSensorDescription[S2107](
        key="temperature_1",
        device_types=(S2107,),
        value_fn=lambda device: device.temperature(1),
        translation_key="probe_temperature",
        translation_placeholders={"probe": "1"},
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2107](
        key="temperature_2",
        device_types=(S2107,),
        value_fn=lambda device: device.temperature(2),
        translation_key="probe_temperature",
        translation_placeholders={"probe": "2"},
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2107](
        key="temperature_3",
        device_types=(S2107,),
        value_fn=lambda device: device.temperature(3),
        translation_key="probe_temperature",
        translation_placeholders={"probe": "3"},
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[SenseCapDevice](
        key="battery",
        device_types=(
            S2101,
            S2102,
            S2103,
            S2104,
            S2105,
            S2106,
            S2107,
            S2120,
        ),
        value_fn=lambda device: (
            battery_level
            if (battery_level := device.battery_level) is not None
            else device.battery_percentage
        ),
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SenseCapConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for existing and newly discovered devices."""

    @callback
    def added(coordinator: SenseCapCoordinator) -> None:
        async_add_entities(
            SenseCapSensor(coordinator, description)
            for description in DESCRIPTIONS
            if isinstance(coordinator.data, description.device_types)
        )

    entry.async_on_unload(entry.runtime_data.subscribe_coordinator_added(added))


class SenseCapSensor(LoRaWANEntity[SenseCapDevice], SensorEntity):
    """Home Assistant entity representing a SenseCAP device datapoint."""

    coordinator: SenseCapCoordinator
    entity_description: SenseCapSensorDescription[Any]

    @property
    @override
    def device_info(self) -> DeviceInfo:
        return self.coordinator.device_info

    @property
    @override
    def native_value(self) -> float | None:
        """Return the last observed measurement."""
        return self.entity_description.value_fn(self.device)
