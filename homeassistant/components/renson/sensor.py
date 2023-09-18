"""Sensor data of the Renson ventilation unit."""
from __future__ import annotations

from dataclasses import dataclass

from renson_endura_delta.field_enum import (
    AIR_QUALITY_FIELD,
    BREEZE_LEVEL_FIELD,
    BREEZE_TEMPERATURE_FIELD,
    BYPASS_LEVEL_FIELD,
    BYPASS_TEMPERATURE_FIELD,
    CO2_FIELD,
    CO2_HYSTERESIS_FIELD,
    CO2_QUALITY_FIELD,
    CO2_THRESHOLD_FIELD,
    CURRENT_AIRFLOW_EXTRACT_FIELD,
    CURRENT_AIRFLOW_INGOING_FIELD,
    CURRENT_LEVEL_FIELD,
    DAY_POLLUTION_FIELD,
    DAYTIME_FIELD,
    FILTER_REMAIN_FIELD,
    HUMIDITY_FIELD,
    INDOOR_TEMP_FIELD,
    MANUAL_LEVEL_FIELD,
    NIGHT_POLLUTION_FIELD,
    NIGHTTIME_FIELD,
    OUTDOOR_TEMP_FIELD,
    FieldEnum,
)
from renson_endura_delta.renson import RensonVentilation

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RensonCoordinator, RensonData
from .const import DOMAIN
from .entity import RensonEntity

OPTIONS_MAPPING = {
    "Off": "off",
    "Level1": "level1",
    "Level2": "level2",
    "Level3": "level3",
    "Level4": "level4",
    "Breeze": "breeze",
    "Holiday": "holiday",
}


@dataclass
class RensonSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    field: FieldEnum
    raw_format: bool


@dataclass
class RensonSensorEntityDescription(
    SensorEntityDescription, RensonSensorEntityDescriptionMixin
):
    """Description of a Renson sensor."""


SENSORS: tuple[RensonSensorEntityDescription, ...] = (
    RensonSensorEntityDescription(
        key="CO2_QUALITY_FIELD",
        translation_key="co2_quality_category",
        field=CO2_QUALITY_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.ENUM,
        options=["good", "bad", "poor"],
    ),
    RensonSensorEntityDescription(
        key="AIR_QUALITY_FIELD",
        translation_key="air_quality_category",
        field=AIR_QUALITY_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.ENUM,
        options=["good", "bad", "poor"],
    ),
    RensonSensorEntityDescription(
        key="CO2_FIELD",
        field=CO2_FIELD,
        raw_format=True,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    RensonSensorEntityDescription(
        key="AIR_FIELD",
        translation_key="air_quality",
        field=AIR_QUALITY_FIELD,
        state_class=SensorStateClass.MEASUREMENT,
        raw_format=True,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    RensonSensorEntityDescription(
        key="CURRENT_LEVEL_FIELD",
        translation_key="ventilation_level",
        field=CURRENT_LEVEL_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3", "level4", "breeze", "holiday"],
    ),
    RensonSensorEntityDescription(
        key="CURRENT_AIRFLOW_EXTRACT_FIELD",
        translation_key="total_airflow_out",
        field=CURRENT_AIRFLOW_EXTRACT_FIELD,
        raw_format=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    ),
    RensonSensorEntityDescription(
        key="CURRENT_AIRFLOW_INGOING_FIELD",
        translation_key="total_airflow_in",
        field=CURRENT_AIRFLOW_INGOING_FIELD,
        raw_format=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    ),
    RensonSensorEntityDescription(
        key="OUTDOOR_TEMP_FIELD",
        translation_key="outdoor_air_temperature",
        field=OUTDOOR_TEMP_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    RensonSensorEntityDescription(
        key="INDOOR_TEMP_FIELD",
        translation_key="extract_air_temperature",
        field=INDOOR_TEMP_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    RensonSensorEntityDescription(
        key="FILTER_REMAIN_FIELD",
        translation_key="filter_change",
        field=FILTER_REMAIN_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
    RensonSensorEntityDescription(
        key="HUMIDITY_FIELD",
        field=HUMIDITY_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    RensonSensorEntityDescription(
        key="MANUAL_LEVEL_FIELD",
        translation_key="manual_level",
        field=MANUAL_LEVEL_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3", "level4", "breeze", "holiday"],
    ),
    RensonSensorEntityDescription(
        key="BREEZE_TEMPERATURE_FIELD",
        translation_key="breeze_temperature",
        field=BREEZE_TEMPERATURE_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="BREEZE_LEVEL_FIELD",
        translation_key="breeze_level",
        field=BREEZE_LEVEL_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3", "level4", "breeze"],
    ),
    RensonSensorEntityDescription(
        key="DAYTIME_FIELD",
        translation_key="start_day_time",
        field=DAYTIME_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="NIGHTTIME_FIELD",
        translation_key="start_night_time",
        field=NIGHTTIME_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="DAY_POLLUTION_FIELD",
        translation_key="day_pollution_level",
        field=DAY_POLLUTION_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=["level1", "level2", "level3", "level4"],
    ),
    RensonSensorEntityDescription(
        key="NIGHT_POLLUTION_FIELD",
        translation_key="co2_quality_category",
        field=NIGHT_POLLUTION_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=["level1", "level2", "level3", "level4"],
    ),
    RensonSensorEntityDescription(
        key="CO2_THRESHOLD_FIELD",
        translation_key="co2_threshold",
        field=CO2_THRESHOLD_FIELD,
        raw_format=False,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="CO2_HYSTERESIS_FIELD",
        translation_key="co2_hysteresis",
        field=CO2_HYSTERESIS_FIELD,
        raw_format=False,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="BYPASS_TEMPERATURE_FIELD",
        translation_key="bypass_activation_temperature",
        field=BYPASS_TEMPERATURE_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    RensonSensorEntityDescription(
        key="BYPASS_LEVEL_FIELD",
        translation_key="bypass_level",
        field=BYPASS_LEVEL_FIELD,
        raw_format=False,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


class RensonSensor(RensonEntity, SensorEntity):
    """Get a sensor data from the Renson API and store it in the state of the class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        description: RensonSensorEntityDescription,
        api: RensonVentilation,
        coordinator: RensonCoordinator,
    ) -> None:
        """Initialize class."""
        super().__init__(description.key, api, coordinator)

        self.field = description.field
        self.entity_description = description

        self.data_type = description.field.field_type
        self.raw_format = description.raw_format

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        all_data = self.coordinator.data

        value = self.api.get_field_value(all_data, self.field.name)

        if self.raw_format:
            self._attr_native_value = value
        elif self.entity_description.device_class == SensorDeviceClass.ENUM:
            self._attr_native_value = OPTIONS_MAPPING.get(
                self.api.parse_value(value, self.data_type), None
            )
        else:
            self._attr_native_value = self.api.parse_value(value, self.data_type)

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renson sensor platform."""

    data: RensonData = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        RensonSensor(description, data.api, data.coordinator) for description in SENSORS
    ]

    async_add_entities(entities)
