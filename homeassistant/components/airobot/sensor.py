"""Sensor platform for Airobot thermostat and ventilation unit."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override

from pyairobotmodbus.models import AirobotData
from pyairobotrest.models import ThermostatStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfDensity,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow
from homeassistant.util.variance import ignore_variance

from .coordinator import (
    AirobotConfigEntry,
    AirobotDataUpdateCoordinator,
    AirobotVUCoordinator,
)
from .entity import AirobotEntity, AirobotVUEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirobotSensorEntityDescription(SensorEntityDescription):
    """Describes Airobot sensor entity."""

    value_fn: Callable[[ThermostatStatus], StateType | datetime]
    supported_fn: Callable[[ThermostatStatus], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class AirobotVUSensorEntityDescription(SensorEntityDescription):
    """Describes Airobot VU sensor entity."""

    value_fn: Callable[[AirobotData], StateType]
    supported_fn: Callable[[AirobotData], bool] = lambda _: True


uptime_to_stable_datetime = ignore_variance(
    lambda value: utcnow().replace(microsecond=0) - timedelta(seconds=value),
    timedelta(minutes=2),
)

SENSOR_TYPES: tuple[AirobotSensorEntityDescription, ...] = (
    AirobotSensorEntityDescription(
        key="air_temperature",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda status: status.temp_air,
    ),
    AirobotSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.hum_air,
    ),
    AirobotSensorEntityDescription(
        key="floor_temperature",
        translation_key="floor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.temp_floor,
        supported_fn=lambda status: status.has_floor_sensor,
    ),
    AirobotSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.co2,
        supported_fn=lambda status: status.has_co2_sensor,
    ),
    AirobotSensorEntityDescription(
        key="air_quality_index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.aqi,
        supported_fn=lambda status: status.has_co2_sensor,
    ),
    AirobotSensorEntityDescription(
        key="heating_uptime",
        translation_key="heating_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.heating_uptime,
        entity_registry_enabled_default=False,
    ),
    AirobotSensorEntityDescription(
        key="errors",
        translation_key="errors",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.errors,
    ),
    AirobotSensorEntityDescription(
        key="device_uptime",
        translation_key="device_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: uptime_to_stable_datetime(status.device_uptime),
        entity_registry_enabled_default=False,
    ),
)

VU_SENSOR_TYPES: tuple[AirobotVUSensorEntityDescription, ...] = (
    # Temperatures
    AirobotVUSensorEntityDescription(
        key="extract_air_temperature",
        translation_key="extract_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.extract_air_temp,
    ),
    AirobotVUSensorEntityDescription(
        key="supply_air_temperature",
        translation_key="supply_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.supply_air_temp,
    ),
    AirobotVUSensorEntityDescription(
        key="outside_air_temperature",
        translation_key="outside_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.outside_air_temp,
    ),
    AirobotVUSensorEntityDescription(
        key="exhaust_air_temperature",
        translation_key="exhaust_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.exhaust_air_temp,
    ),
    AirobotVUSensorEntityDescription(
        key="extra_temperature",
        translation_key="extra_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.extra_temp,
        supported_fn=lambda data: data.extra_temp is not None,
    ),
    # Humidity
    AirobotVUSensorEntityDescription(
        key="extract_air_humidity",
        translation_key="extract_air_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.extract_air_humidity,
    ),
    AirobotVUSensorEntityDescription(
        key="supply_air_humidity",
        translation_key="supply_air_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.supply_air_humidity,
    ),
    AirobotVUSensorEntityDescription(
        key="outside_air_humidity",
        translation_key="outside_air_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.outside_air_humidity,
    ),
    AirobotVUSensorEntityDescription(
        key="exhaust_air_humidity",
        translation_key="exhaust_air_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.exhaust_air_humidity,
    ),
    AirobotVUSensorEntityDescription(
        key="extra_humidity",
        translation_key="extra_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.extra_humidity,
        supported_fn=lambda data: data.extra_humidity is not None,
    ),
    # Air quality
    AirobotVUSensorEntityDescription(
        key="co2_level",
        translation_key="co2_level",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.co2_level,
    ),
    AirobotVUSensorEntityDescription(
        key="voc",
        translation_key="voc",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.voc,
    ),
    AirobotVUSensorEntityDescription(
        key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.pm25,
    ),
    # Fan
    AirobotVUSensorEntityDescription(
        key="supply_fan_rpm",
        translation_key="supply_fan_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        value_fn=lambda data: data.supply_fan_rpm,
    ),
    AirobotVUSensorEntityDescription(
        key="extract_fan_rpm",
        translation_key="extract_fan_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        value_fn=lambda data: data.extract_fan_rpm,
    ),
    AirobotVUSensorEntityDescription(
        key="supply_fan_level",
        translation_key="supply_fan_level",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.supply_fan_level,
    ),
    AirobotVUSensorEntityDescription(
        key="extract_fan_level",
        translation_key="extract_fan_level",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.extract_fan_level,
    ),
    AirobotVUSensorEntityDescription(
        key="supply_airflow",
        translation_key="supply_airflow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        # Only constant-flow models measure airflow
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.supply_airflow,
    ),
    AirobotVUSensorEntityDescription(
        key="extract_airflow",
        translation_key="extract_airflow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.extract_airflow,
    ),
    # Device
    AirobotVUSensorEntityDescription(
        key="heat_recovery_efficiency",
        translation_key="heat_recovery_efficiency",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        value_fn=lambda data: data.heat_recovery_efficiency,
    ),
    AirobotVUSensorEntityDescription(
        key="working_time",
        translation_key="working_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.working_time_ms,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Airobot sensor platform."""
    coordinator = entry.runtime_data
    if isinstance(coordinator, AirobotVUCoordinator):
        async_add_entities(
            AirobotVUSensor(coordinator, description)
            for description in VU_SENSOR_TYPES
            if description.supported_fn(coordinator.data)
        )
        return

    async_add_entities(
        AirobotSensor(coordinator, description)
        for description in SENSOR_TYPES
        if description.supported_fn(coordinator.data.status)
    )


class AirobotSensor(AirobotEntity, SensorEntity):
    """Representation of an Airobot sensor."""

    entity_description: AirobotSensorEntityDescription

    def __init__(
        self,
        coordinator: AirobotDataUpdateCoordinator,
        description: AirobotSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.status.device_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.status)


class AirobotVUSensor(AirobotVUEntity, SensorEntity):
    """Representation of an Airobot VU sensor."""

    entity_description: AirobotVUSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
