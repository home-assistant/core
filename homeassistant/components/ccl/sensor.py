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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CCLConfigEntry, CCLCoordinator
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
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        native_unit_of_measurement=DEGREE,
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
        options=["thermo-hygro", "pool", "soil"],
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
    CCLSensorTypes.VOC_LEVEL: SensorEntityDescription(
        key="VOC_LEVEL",
        translation_key="voc_level",
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
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="aqi",
    ),
    CCLSensorTypes.BATTERY: SensorEntityDescription(
        key="BATTERY",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for passed config entry in HA."""
    coordinator = entry.runtime_data

    def _new_sensors(sensors: list[CCLSensor]) -> bool:
        """Add sensors to the data entry."""
        sensor_entities = []

        for sensor in sensors:
            if sensor.sensor_type in CCL_SENSOR_DESCRIPTIONS:
                entity_description = dataclasses.replace(
                    CCL_SENSOR_DESCRIPTIONS[sensor.sensor_type],
                    key=sensor.key,
                    name=sensor.name,
                )
                sensor_entities.append(CCLSensorEntity(coordinator, entity_description))

        async_add_entities(sensor_entities)

        return True

    coordinator.device.set_new_sensor_callback(_new_sensors)

    if coordinator.data is not None:
        _new_sensors(coordinator.data.values())


class CCLSensorEntity(CCLEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self,
        coordinator: CCLCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize a CCL Sensor Entity."""
        self._internal: CCLSensor = coordinator.data[entity_description.key]
        super().__init__(self._internal, coordinator)

        self.entity_description = entity_description

    @property
    def native_value(self) -> int | float | str:
        """Return the state of the sensor."""
        return self._internal.value
