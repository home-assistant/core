"""Support for Ecowitt Weather Stations."""
from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Final

from aioecowitt import EcoWittListener, EcoWittSensor, EcoWittSensorTypes

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UV_INDEX,
    UnitOfElectricPotential,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from .const import DOMAIN
from .entity import EcowittEntity

_METRIC: Final = (
    EcoWittSensorTypes.TEMPERATURE_C,
    EcoWittSensorTypes.RAIN_COUNT_MM,
    EcoWittSensorTypes.RAIN_RATE_MM,
    EcoWittSensorTypes.LIGHTNING_DISTANCE_KM,
    EcoWittSensorTypes.SPEED_KPH,
    EcoWittSensorTypes.PRESSURE_HPA,
)
_IMPERIAL: Final = (
    EcoWittSensorTypes.TEMPERATURE_F,
    EcoWittSensorTypes.RAIN_COUNT_INCHES,
    EcoWittSensorTypes.RAIN_RATE_INCHES,
    EcoWittSensorTypes.LIGHTNING_DISTANCE_MILES,
    EcoWittSensorTypes.SPEED_MPH,
    EcoWittSensorTypes.PRESSURE_INHG,
)


ECOWITT_SENSORS_MAPPING: Final = {
    EcoWittSensorTypes.HUMIDITY: SensorEntityDescription(
        key="HUMIDITY",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.DEGREE: SensorEntityDescription(
        key="DEGREE", native_unit_of_measurement=DEGREE
    ),
    EcoWittSensorTypes.WATT_METERS_SQUARED: SensorEntityDescription(
        key="WATT_METERS_SQUARED",
        device_class=SensorDeviceClass.IRRADIANCE,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.UV_INDEX: SensorEntityDescription(
        key="UV_INDEX",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.PM25: SensorEntityDescription(
        key="PM25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.PM10: SensorEntityDescription(
        key="PM10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.BATTERY_PERCENTAGE: SensorEntityDescription(
        key="BATTERY_PERCENTAGE",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.BATTERY_VOLTAGE: SensorEntityDescription(
        key="BATTERY_VOLTAGE",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.CO2_PPM: SensorEntityDescription(
        key="CO2_PPM",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.LUX: SensorEntityDescription(
        key="LUX",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.TIMESTAMP: SensorEntityDescription(
        key="TIMESTAMP", device_class=SensorDeviceClass.TIMESTAMP
    ),
    EcoWittSensorTypes.VOLTAGE: SensorEntityDescription(
        key="VOLTAGE",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.LIGHTNING_COUNT: SensorEntityDescription(
        key="LIGHTNING_COUNT",
        native_unit_of_measurement="strikes",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcoWittSensorTypes.TEMPERATURE_C: SensorEntityDescription(
        key="TEMPERATURE_C",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.TEMPERATURE_F: SensorEntityDescription(
        key="TEMPERATURE_F",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.RAIN_COUNT_MM: SensorEntityDescription(
        key="RAIN_COUNT_MM",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcoWittSensorTypes.RAIN_COUNT_INCHES: SensorEntityDescription(
        key="RAIN_COUNT_INCHES",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcoWittSensorTypes.RAIN_RATE_MM: SensorEntityDescription(
        key="RAIN_RATE_MM",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    EcoWittSensorTypes.RAIN_RATE_INCHES: SensorEntityDescription(
        key="RAIN_RATE_INCHES",
        native_unit_of_measurement=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    EcoWittSensorTypes.LIGHTNING_DISTANCE_KM: SensorEntityDescription(
        key="LIGHTNING_DISTANCE_KM",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.LIGHTNING_DISTANCE_MILES: SensorEntityDescription(
        key="LIGHTNING_DISTANCE_MILES",
        native_unit_of_measurement=UnitOfLength.MILES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.SPEED_KPH: SensorEntityDescription(
        key="SPEED_KPH",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.SPEED_MPH: SensorEntityDescription(
        key="SPEED_MPH",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.PRESSURE_HPA: SensorEntityDescription(
        key="PRESSURE_HPA",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.PRESSURE_INHG: SensorEntityDescription(
        key="PRESSURE_INHG",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.INHG,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoWittSensorTypes.PERCENTAGE: SensorEntityDescription(
        key="PERCENTAGE",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add sensors if new."""
    ecowitt: EcoWittListener = hass.data[DOMAIN][entry.entry_id]

    def _new_sensor(sensor: EcoWittSensor) -> None:
        """Add new sensor."""
        if sensor.stype not in ECOWITT_SENSORS_MAPPING:
            return

        # Ignore metrics that are not supported by the user's locale
        if sensor.stype in _METRIC and hass.config.units is not METRIC_SYSTEM:
            return
        if sensor.stype in _IMPERIAL and hass.config.units is not US_CUSTOMARY_SYSTEM:
            return
        mapping = ECOWITT_SENSORS_MAPPING[sensor.stype]

        # Setup sensor description
        description = dataclasses.replace(
            mapping,
            key=sensor.key,
            name=sensor.name,
        )

        # Hourly rain doesn't reset to fixed hours, it must be measurement state classes
        if sensor.key in ("hrain_piezomm", "hrain_piezo"):
            description = dataclasses.replace(
                description,
                state_class=SensorStateClass.MEASUREMENT,
            )

        async_add_entities([EcowittSensorEntity(sensor, description)])

    ecowitt.new_sensor_cb.append(_new_sensor)
    entry.async_on_unload(lambda: ecowitt.new_sensor_cb.remove(_new_sensor))

    # Add all sensors that are already known
    for sensor in ecowitt.sensors.values():
        _new_sensor(sensor)


class EcowittSensorEntity(EcowittEntity, SensorEntity):
    """Representation of a Ecowitt Sensor."""

    def __init__(
        self, sensor: EcoWittSensor, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(sensor)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.ecowitt.value
