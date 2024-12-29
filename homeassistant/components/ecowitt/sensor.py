"""Support for Ecowitt Weather Stations."""

from __future__ import annotations

import dataclasses
from datetime import datetime
import logging
from typing import Final

from aioecowitt import EcoWittSensor, EcoWittSensorTypes, EcoWittStation
from aioecowitt.sensor import SENSOR_MAP

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UV_INDEX,
    EntityCategory,
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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from . import EcowittConfigEntry
from .entity import EcowittEntity

_LOGGER = logging.getLogger(__name__)
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
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EcoWittSensorTypes.BATTERY_VOLTAGE: SensorEntityDescription(
        key="BATTERY_VOLTAGE",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
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
        entity_category=EntityCategory.DIAGNOSTIC,
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
    EcoWittSensorTypes.SOIL_RAWADC: SensorEntityDescription(
        key="SOIL_RAWADC",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
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


def get_sensor_key_by_name(name: str) -> str | None:
    """Retrieve the sensor key from SENSOR_MAP by its name.

    Args:
        name (str): The name of the sensor.

    Returns:
        str | None: The corresponding key if found, otherwise None.

    """
    for key, mapping in SENSOR_MAP.items():
        if mapping.name == name:
            return key
    return None


def get_sensor_stype_by_name(name: str) -> EcoWittSensorTypes | None:
    """Retrieve the sensor type (stype) from SENSOR_MAP by its name.

    Args:
        name (str): The name of the sensor.

    Returns:
        EcoWittSensorTypes | None: The corresponding sensor type if found, otherwise None.

    """
    for mapping in SENSOR_MAP.values():
        if mapping.name == name:
            return mapping.stype
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcowittConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ecowitt sensors from a config entry."""
    ecowitt = entry.runtime_data
    entities = []

    def _new_sensor(sensor: EcoWittSensor) -> None:
        """Add a new sensor entity."""
        _LOGGER.debug("_new_sensor: %s", sensor)
        _LOGGER.debug("_new_sensor.stype: %s", sensor.stype)
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

        # Adjust specific configurations for hourly rain sensors
        if sensor.key in (
            "hrain_piezomm",
            "hrain_piezo",
            "hourlyrainmm",
            "hourlyrainin",
        ):
            description = dataclasses.replace(
                description,
                state_class=SensorStateClass.MEASUREMENT,
            )

        _LOGGER.debug("stype_original: %s", sensor.stype)
        async_add_entities([EcowittSensorEntity(sensor, description)])

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    _LOGGER.debug("entries: %s", entries)
    # Restore entities from the entity registry
    for config_entry in entries:
        _LOGGER.debug("config_entry: %s", config_entry)

        # Simulate a sensor for restoration
        _LOGGER.debug("stype: %s", get_sensor_key_by_name(config_entry.original_name))
        _LOGGER.debug("config_entry.original_name: %s", config_entry.original_name)
        _LOGGER.debug("config_entry: %s", config_entry)

        fake_sensor = EcoWittSensor(
            name=config_entry.original_name,
            key=config_entry.unique_id.split("-")[1],
            stype=get_sensor_key_by_name(config_entry.original_name),
            station=EcoWittStation(
                station="GW2000A_V3.1.6",
                model="GW2000A",
                frequence="868M",
                key="9835D60D7F0BDF05A99FC269236C3079",
                version="126",
            ),
        )
        mapping = ECOWITT_SENSORS_MAPPING[
            get_sensor_stype_by_name(config_entry.original_name)
        ]

        # Setup sensor description
        description = dataclasses.replace(
            mapping,
            key=fake_sensor.key,
            name=fake_sensor.name,
        )
        if fake_sensor.key in (
            "hrain_piezomm",
            "hrain_piezo",
            "hourlyrainmm",
            "hourlyrainin",
        ):
            description = dataclasses.replace(
                description,
                state_class=SensorStateClass.MEASUREMENT,
            )
        _LOGGER.debug("description.key: %s", description.key)
        _LOGGER.debug("fake_sensor.key: %s", fake_sensor.key)
        _LOGGER.debug(
            "config_entry.unique_id.split()[1]: %s",
            config_entry.unique_id.split("-")[1],
        )
        _LOGGER.debug("fake_sensor: %s", fake_sensor)
        entities.append(EcowittSensorEntity(fake_sensor, description=description))
    _LOGGER.debug("entities: %s", entities)
    async_add_entities(entities)
    # Add new sensors from the Ecowitt runtime data
    ecowitt.new_sensor_cb.append(_new_sensor)
    entry.async_on_unload(lambda: ecowitt.new_sensor_cb.remove(_new_sensor))

    _LOGGER.debug("ecowitt.sensors.values(): %s", ecowitt.sensors.values())
    for sensor in ecowitt.sensors.values():
        _LOGGER.debug("Adding existing sensor: %s", sensor)
        _new_sensor(sensor)

    # Add entities to Home Assistant


class EcowittSensorEntity(EcowittEntity, RestoreSensor):
    """Representation of a Ecowitt Sensor."""

    def __init__(
        self, sensor: EcoWittSensor, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(sensor)
        self.entity_description = description
        self.test = None
        _LOGGER.debug("EcowittSensor: %s", sensor)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.ecowitt.value

    # async def async_added_to_hass(self) -> None:
    #     """Call when entity about to be added to hass."""
    #     # If not None, we got an initial value.
    #     await super().async_added_to_hass()
    #     if self._attr_native_value is not None:
    #         return

    #     if (sensor_data := await self.async_get_last_sensor_data()) is not None:
    #         _LOGGER.debug("sensor_data: %s", sensor_data)
    #         self._attr_native_value = sensor_data.native_value
