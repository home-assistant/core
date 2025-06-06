"""Support for Ecowitt Weather Stations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Any, Final

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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from . import EcowittConfigEntry
from .entity import EcowittEntity

MAX_AGE = 300

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
        key="DEGREE",
        native_unit_of_measurement=DEGREE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
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


@dataclass
class SensorInfo:
    """Represents information about an Ecowitt sensor, including its key and type."""

    key: str
    stype: EcoWittSensorTypes


SENSOR_INFO_BY_NAME = {
    mapping.name: SensorInfo(key, mapping.stype) for key, mapping in SENSOR_MAP.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcowittConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors if new."""
    ecowitt = entry.runtime_data
    entities: list[EcowittSensorEntity] = []
    added_keys = set()

    def _generate_entity(sensor: EcoWittSensor, mapping: Any) -> EcowittSensorEntity:
        # Setup sensor description
        description = replace(
            mapping,
            key=sensor.key,
            name=sensor.name,
        )

        # Hourly rain doesn't reset to fixed hours, it must be measurement state classes
        if sensor.key in (
            "hrain_piezomm",
            "hrain_piezo",
            "hourlyrainmm",
            "hourlyrainin",
        ):
            description = replace(
                description,
                state_class=SensorStateClass.MEASUREMENT,
            )

        return EcowittSensorEntity(sensor, description)

    def _new_sensor(*sensors: EcoWittSensor) -> None:
        """Add new sensor entities if they don't already exist."""
        new_sensor_entities: list[EcowittSensorEntity] = []
        for sensor in sensors:
            if sensor.key in added_keys:
                _LOGGER.debug("Sensor already added: %s", sensor.key)
                continue

            if sensor.stype not in ECOWITT_SENSORS_MAPPING:
                continue

            # Ignore metrics that are not supported by the user's locale
            if sensor.stype in _METRIC and hass.config.units is not METRIC_SYSTEM:
                continue
            if (
                sensor.stype in _IMPERIAL
                and hass.config.units is not US_CUSTOMARY_SYSTEM
            ):
                continue

            mapping = ECOWITT_SENSORS_MAPPING[sensor.stype]
            entity = _generate_entity(sensor, mapping)
            new_sensor_entities.append(entity)
            added_keys.add(sensor.key)
        async_add_entities(new_sensor_entities)

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    # Restore entities from the entity registry
    for config_entry in entries:
        if config_entry.original_name is not None:
            config_entry_unique_id = config_entry.unique_id.split("-")[0]
            config_entry_key = config_entry.unique_id.split("-")[1]
            sensor_info = SENSOR_INFO_BY_NAME.get(config_entry.original_name)
            if sensor_info is None:
                return
            sensor_key_name = sensor_info.key
            station = EcoWittStation(
                **entry.data["station"],
            )
            sensor = ecowitt.sensors[f"{config_entry_unique_id}.{sensor_key_name}"] = (
                EcoWittSensor(
                    name=config_entry.original_name,
                    key=config_entry_key,
                    stype=sensor_key_name,  # type: ignore[arg-type]
                    station=station,
                )
            )
            stype = sensor_info.stype
            mapping = ECOWITT_SENSORS_MAPPING[stype]
            entity = _generate_entity(sensor, mapping)
            entities.append(entity)
            added_keys.add(config_entry_key)

    async_add_entities(entities)

    # Add new sensors dynamically from webhook data
    ecowitt.new_sensor_cb.append(_new_sensor)
    entry.async_on_unload(lambda: ecowitt.new_sensor_cb.remove(_new_sensor))

    # Add all sensors that are already known
    _new_sensor(*ecowitt.sensors.values())


class EcowittSensorEntity(EcowittEntity, RestoreSensor):
    """Representation of a Ecowitt Sensor."""

    def __init__(
        self, sensor: EcoWittSensor, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(sensor)
        self.entity_description = description
        self.restored_value: StateType | datetime | date | Decimal = None
        self.restored_last_reported: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        if self._attr_native_value is not None:
            return
        if (sensor_last_state := await self.async_get_last_state()) is not None:
            self.restored_last_reported = sensor_last_state.last_reported

        if (sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = sensor_data.native_value
            self._attr_available = True
            self.restored_value = sensor_data.native_value
            self.hass.async_create_background_task(
                self.check_availability(), self.entity_id
            )

    @property
    def native_value(self) -> StateType | datetime | date | Decimal:
        """Return the state of the sensor."""
        if self.ecowitt.value is not None:
            return self.ecowitt.value
        return self.restored_value

    @property
    def available(self) -> bool:
        """Return whether the state is based on actual reading from device."""
        if self.ecowitt.value is not None:
            return super().available
        if self.restored_last_reported:
            age = dt_util.utcnow() - self.restored_last_reported
            if age.seconds >= MAX_AGE:
                return False
            if age.seconds < MAX_AGE:
                return True
        return False

    async def check_availability(self) -> None:
        """Return whether the state is based on actual reading from device."""
        if not self.restored_last_reported:
            self._attr_available = False
            self.async_write_ha_state()
            return

        age = dt_util.utcnow() - self.restored_last_reported
        _LOGGER.debug("%s was last reported %is ago", self.entity_id, age.seconds)
        await asyncio.sleep(MAX_AGE - age.seconds)
        new_age = dt_util.utcnow() - self.restored_last_reported
        if new_age.seconds >= MAX_AGE:
            self._attr_available = False
            self.async_write_ha_state()
