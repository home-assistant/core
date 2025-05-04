"""Platform for sensor integration."""

from __future__ import annotations

import dataclasses

from aioccl import CCLSensor, CCLSensorTypes

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
    DEGREE,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CCLConfigEntry
from .coordinator import CCLCoordinator
from .entity import CCLEntity

PARALLEL_UPDATES = 0

CCL_SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    CCLSensorTypes.PRESSURE: SensorEntityDescription(
        key="PRESSURE",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
    ),
    CCLSensorTypes.TEMPERATURE: SensorEntityDescription(
        key="TEMPERATURE",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CCLSensorTypes.HUMIDITY: SensorEntityDescription(
        key="HUMIDITY",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    CCLSensorTypes.WIND_DIRECITON: SensorEntityDescription(
        key="WIND_DIRECTION",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,
        translation_key="wind_direction",
    ),
    CCLSensorTypes.WIND_SPEED: SensorEntityDescription(
        key="WIND_SPEED",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    ),
    CCLSensorTypes.RAIN_RATE: SensorEntityDescription(
        key="RAIN_RATE",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
    ),
    CCLSensorTypes.RAINFALL: SensorEntityDescription(
        key="RAINFALL",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
    ),
    CCLSensorTypes.UVI: SensorEntityDescription(
        key="UVI",
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="uvi",
    ),
    CCLSensorTypes.RADIATION: SensorEntityDescription(
        key="RADIATION",
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
    ),
    CCLSensorTypes.CH_SENSOR_TYPE: SensorEntityDescription(
        key="CH_SENSOR_TYPE",
        device_class=SensorDeviceClass.ENUM,
    ),
    CCLSensorTypes.CO: SensorEntityDescription(
        key="CO",
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    CCLSensorTypes.CO2: SensorEntityDescription(
        key="CO2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    CCLSensorTypes.VOLATILE: SensorEntityDescription(
        key="VOLATILE",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
    ),
    CCLSensorTypes.VOC: SensorEntityDescription(
        key="VOC",
        translation_key="voc",
    ),
    CCLSensorTypes.PM10: SensorEntityDescription(
        key="PM10",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CCLSensorTypes.PM25: SensorEntityDescription(
        key="PM25",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CCLSensorTypes.AQI: SensorEntityDescription(
        key="AQI",
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="aqi",
    ),
    CCLSensorTypes.BATTERY: SensorEntityDescription(
        key="BATTERY",
        translation_key="battery",
    ),
    CCLSensorTypes.LIGHTNING_DISTANCE: SensorEntityDescription(
        key="LIGHTNING_DISTANCE",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        translation_key="lightning_distance",
    ),
    CCLSensorTypes.LIGHTNING_DURATION: SensorEntityDescription(
        key="LIGHTNING_DURATION",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key="lightning_duration",
    ),
    CCLSensorTypes.LIGHTNING_FREQUENCY: SensorEntityDescription(
        key="LIGHTNING_FREQUENCY",
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="lightning_frequency",
    ),
    CCLSensorTypes.BATTERY_VOLTAGE: SensorEntityDescription(
        key="BATTERY_VOLTAGE",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CCLConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config entry in HA."""
    coordinator = entry.runtime_data

    def _new_sensor(sensor: CCLSensor) -> None:
        """Add a sensor to the data entry."""
        entity_description = dataclasses.replace(
            CCL_SENSOR_DESCRIPTIONS[sensor.sensor_type],
            key=sensor.key,
            name=sensor.name,
        )
        async_add_entities([CCLSensorEntity(coordinator, entity_description)])

    coordinator.device.register_new_sensor_cb(_new_sensor)
    entry.async_on_unload(lambda: coordinator.device.remove_new_sensor_cb(_new_sensor))

    if coordinator.data is not None:
        if "sensors" in coordinator.data:
            for sensor in coordinator.data["sensors"].values():
                _new_sensor(sensor)


class CCLSensorEntity(CCLEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self,
        coordinator: CCLCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize a CCL Sensor Entity."""
        self._internal: CCLSensor = coordinator.data["sensors"][entity_description.key]
        super().__init__(self._internal, coordinator)

        self.entity_description = entity_description

    @property
    def native_value(self) -> None | str | int | float:
        """Return the state of the sensor."""
        return self._internal.value
