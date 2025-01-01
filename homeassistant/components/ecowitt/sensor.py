"""Support for Ecowitt Weather Stations."""

from __future__ import annotations

import dataclasses
from datetime import datetime
import logging
from typing import Final
from aioecowitt import EcoWittSensor, EcoWittSensorTypes, EcoWittStation
from aioecowitt.sensor import SENSOR_MAP
from homeassistant.const import CONF_WEBHOOK_ID
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

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from . import EcowittConfigEntry
from .entity import EcowittEntity
from .const import DOMAIN

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
    added_keys = set()  # Track keys of already added entities

    def _new_sensor(sensor: EcoWittSensor) -> None:
        """Add a new sensor entity if it doesn't already exist."""
        if sensor.key in added_keys:
            _LOGGER.debug("Sensor already added: %s", sensor.key)
            return

        if sensor.stype not in ECOWITT_SENSORS_MAPPING:
            return

        # Ignore unsupported locale metrics
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

        entity = EcowittSensorEntity(sensor, description)
        entities.append(entity)
        added_keys.add(sensor.key)
        async_add_entities([entity])

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    # Restore entities from the entity registry
    for config_entry in entries:
        config_entry_unique_id = config_entry.unique_id.split("-")[0]
        _LOGGER.debug("config_entry_unique_id %s", config_entry_unique_id)
        config_entry_key = config_entry.unique_id.split("-")[1]
        _LOGGER.debug("config_entry_key: %s", config_entry_key)
        sensor_key_name = get_sensor_key_by_name(config_entry.original_name)
        _LOGGER.debug("entry.data: %s", entry.data)
        station = EcoWittStation(
            **entry.data["station"],
        )
        sensor = ecowitt.sensors[f"{config_entry_unique_id}.{sensor_key_name}"] = (
            EcoWittSensor(
                name=config_entry.original_name,
                key=config_entry_key,
                stype=sensor_key_name,
                station=station,
            )
        )
        mapping = ECOWITT_SENSORS_MAPPING[
            get_sensor_stype_by_name(config_entry.original_name)
        ]
        description = dataclasses.replace(
            mapping,
            key=sensor.key,
            name=sensor.name,
        )
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
        entity = EcowittSensorEntity(sensor, description)
        entities.append(entity)
        added_keys.add(config_entry_key)

    async_add_entities(entities)

    # Add new sensors dynamically from webhook data
    ecowitt.new_sensor_cb.append(_new_sensor)
    entry.async_on_unload(lambda: ecowitt.new_sensor_cb.remove(_new_sensor))
    _LOGGER.debug("ecowitt.sensors.values(): %s", ecowitt.sensors.values())
    for sensor in ecowitt.sensors.values():
        _LOGGER.debug("Adding existing sensor: %s", sensor)
        _new_sensor(sensor)


class EcowittSensorEntity(EcowittEntity, RestoreSensor):
    """Representation of a Ecowitt Sensor."""

    def __init__(
        self,
        sensor: EcoWittSensor,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(sensor)
        self.entity_description = description
        self.restored_value = None

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        # If not None, we got an initial value.
        await super().async_added_to_hass()
        if self._attr_native_value is not None:
            return

        if (sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = sensor_data.native_value
            self.restored_value = sensor_data.native_value

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        if self.ecowitt.value is not None:
            return self.ecowitt.value
        return self.restored_value
