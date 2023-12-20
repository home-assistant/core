"""Support for Xiaomi Mi Air Quality Monitor (PM2.5) and Humidifier."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import logging

from miio import AirQualityMonitor, DeviceException
from miio.gateway.gateway import (
    GATEWAY_MODEL_AC_V1,
    GATEWAY_MODEL_AC_V2,
    GATEWAY_MODEL_AC_V3,
    GATEWAY_MODEL_AQARA,
    GATEWAY_MODEL_EU,
    GatewayException,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    AREA_SQUARE_METERS,
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MODEL,
    CONF_TOKEN,
    LIGHT_LUX,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import VacuumCoordinatorDataAttributes
from .const import (
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRFRESH_A1,
    MODEL_AIRFRESH_T2017,
    MODEL_AIRFRESH_VA2,
    MODEL_AIRFRESH_VA4,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CB1,
    MODEL_AIRPURIFIER_3C,
    MODEL_AIRPURIFIER_4,
    MODEL_AIRPURIFIER_4_LITE_RMA1,
    MODEL_AIRPURIFIER_4_LITE_RMB1,
    MODEL_AIRPURIFIER_4_PRO,
    MODEL_AIRPURIFIER_MA2,
    MODEL_AIRPURIFIER_PRO,
    MODEL_AIRPURIFIER_PRO_V7,
    MODEL_AIRPURIFIER_V2,
    MODEL_AIRPURIFIER_V3,
    MODEL_AIRPURIFIER_ZA1,
    MODEL_FAN_P5,
    MODEL_FAN_V2,
    MODEL_FAN_V3,
    MODEL_FAN_ZA1,
    MODEL_FAN_ZA3,
    MODEL_FAN_ZA4,
    MODEL_FAN_ZA5,
    MODELS_AIR_QUALITY_MONITOR,
    MODELS_HUMIDIFIER_MIIO,
    MODELS_HUMIDIFIER_MIOT,
    MODELS_HUMIDIFIER_MJJSQ,
    MODELS_PURIFIER_MIIO,
    MODELS_PURIFIER_MIOT,
    MODELS_VACUUM,
    ROBOROCK_GENERIC,
    ROCKROBO_GENERIC,
)
from .device import XiaomiCoordinatedMiioEntity, XiaomiMiioEntity
from .gateway import XiaomiGatewayDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Sensor"
UNIT_LUMEN = "lm"

ATTR_ACTUAL_SPEED = "actual_speed"
ATTR_AIR_QUALITY = "air_quality"
ATTR_TVOC = "tvoc"
ATTR_AQI = "aqi"
ATTR_BATTERY = "battery"
ATTR_CARBON_DIOXIDE = "co2"
ATTR_CHARGING = "charging"
ATTR_CONTROL_SPEED = "control_speed"
ATTR_DISPLAY_CLOCK = "display_clock"
ATTR_FAVORITE_SPEED = "favorite_speed"
ATTR_FILTER_LIFE_REMAINING = "filter_life_remaining"
ATTR_FILTER_HOURS_USED = "filter_hours_used"
ATTR_FILTER_LEFT_TIME = "filter_left_time"
ATTR_DUST_FILTER_LIFE_REMAINING = "dust_filter_life_remaining"
ATTR_DUST_FILTER_LIFE_REMAINING_DAYS = "dust_filter_life_remaining_days"
ATTR_UPPER_FILTER_LIFE_REMAINING = "upper_filter_life_remaining"
ATTR_UPPER_FILTER_LIFE_REMAINING_DAYS = "upper_filter_life_remaining_days"
ATTR_FILTER_USE = "filter_use"
ATTR_HUMIDITY = "humidity"
ATTR_ILLUMINANCE = "illuminance"
ATTR_ILLUMINANCE_LUX = "illuminance_lux"
ATTR_LOAD_POWER = "load_power"
ATTR_MOTOR2_SPEED = "motor2_speed"
ATTR_MOTOR_SPEED = "motor_speed"
ATTR_NIGHT_MODE = "night_mode"
ATTR_NIGHT_TIME_BEGIN = "night_time_begin"
ATTR_NIGHT_TIME_END = "night_time_end"
ATTR_PM10 = "pm10_density"
ATTR_PM25 = "pm25"
ATTR_PM25_2 = "pm25_2"
ATTR_POWER = "power"
ATTR_PRESSURE = "pressure"
ATTR_PURIFY_VOLUME = "purify_volume"
ATTR_SENSOR_STATE = "sensor_state"
ATTR_USE_TIME = "use_time"
ATTR_WATER_LEVEL = "water_level"
ATTR_DND_START = "start"
ATTR_DND_END = "end"
ATTR_LAST_CLEAN_TIME = "duration"
ATTR_LAST_CLEAN_AREA = "area"
ATTR_STATUS_CLEAN_TIME = "clean_time"
ATTR_STATUS_CLEAN_AREA = "clean_area"
ATTR_LAST_CLEAN_START = "start"
ATTR_LAST_CLEAN_END = "end"
ATTR_CLEAN_HISTORY_TOTAL_DURATION = "total_duration"
ATTR_CLEAN_HISTORY_TOTAL_AREA = "total_area"
ATTR_CLEAN_HISTORY_COUNT = "count"
ATTR_CLEAN_HISTORY_DUST_COLLECTION_COUNT = "dust_collection_count"
ATTR_CONSUMABLE_STATUS_MAIN_BRUSH_LEFT = "main_brush_left"
ATTR_CONSUMABLE_STATUS_SIDE_BRUSH_LEFT = "side_brush_left"
ATTR_CONSUMABLE_STATUS_FILTER_LEFT = "filter_left"
ATTR_CONSUMABLE_STATUS_SENSOR_DIRTY_LEFT = "sensor_dirty_left"


@dataclass(frozen=True)
class XiaomiMiioSensorDescription(SensorEntityDescription):
    """Class that holds device specific info for a xiaomi aqara or humidifier sensor."""

    attributes: tuple = ()
    parent_key: str | None = None


SENSOR_TYPES = {
    ATTR_TEMPERATURE: XiaomiMiioSensorDescription(
        key=ATTR_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ATTR_HUMIDITY: XiaomiMiioSensorDescription(
        key=ATTR_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ATTR_PRESSURE: XiaomiMiioSensorDescription(
        key=ATTR_PRESSURE,
        name="Pressure",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ATTR_LOAD_POWER: XiaomiMiioSensorDescription(
        key=ATTR_LOAD_POWER,
        name="Load power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    ATTR_WATER_LEVEL: XiaomiMiioSensorDescription(
        key=ATTR_WATER_LEVEL,
        name="Water level",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-check",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_ACTUAL_SPEED: XiaomiMiioSensorDescription(
        key=ATTR_ACTUAL_SPEED,
        name="Actual speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fast-forward",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_CONTROL_SPEED: XiaomiMiioSensorDescription(
        key=ATTR_CONTROL_SPEED,
        name="Control speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fast-forward",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_FAVORITE_SPEED: XiaomiMiioSensorDescription(
        key=ATTR_FAVORITE_SPEED,
        name="Favorite speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fast-forward",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_MOTOR_SPEED: XiaomiMiioSensorDescription(
        key=ATTR_MOTOR_SPEED,
        name="Motor speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fast-forward",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_MOTOR2_SPEED: XiaomiMiioSensorDescription(
        key=ATTR_MOTOR2_SPEED,
        name="Second motor speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fast-forward",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_USE_TIME: XiaomiMiioSensorDescription(
        key=ATTR_USE_TIME,
        name="Use time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:progress-clock",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_ILLUMINANCE: XiaomiMiioSensorDescription(
        key=ATTR_ILLUMINANCE,
        name="Illuminance",
        native_unit_of_measurement=UNIT_LUMEN,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ATTR_ILLUMINANCE_LUX: XiaomiMiioSensorDescription(
        key=ATTR_ILLUMINANCE,
        name="Illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ATTR_AIR_QUALITY: XiaomiMiioSensorDescription(
        key=ATTR_AIR_QUALITY,
        native_unit_of_measurement="AQI",
        icon="mdi:cloud",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ATTR_TVOC: XiaomiMiioSensorDescription(
        key=ATTR_TVOC,
        name="TVOC",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
    ),
    ATTR_PM10: XiaomiMiioSensorDescription(
        key=ATTR_PM10,
        name="PM10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ATTR_PM25: XiaomiMiioSensorDescription(
        key=ATTR_AQI,
        name="PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ATTR_PM25_2: XiaomiMiioSensorDescription(
        key=ATTR_PM25,
        name="PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ATTR_FILTER_LIFE_REMAINING: XiaomiMiioSensorDescription(
        key=ATTR_FILTER_LIFE_REMAINING,
        name="Filter lifetime remaining",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:air-filter",
        state_class=SensorStateClass.MEASUREMENT,
        attributes=("filter_type",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_FILTER_USE: XiaomiMiioSensorDescription(
        key=ATTR_FILTER_HOURS_USED,
        name="Filter use",
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_FILTER_LEFT_TIME: XiaomiMiioSensorDescription(
        key=ATTR_FILTER_LEFT_TIME,
        name="Filter lifetime left",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_DUST_FILTER_LIFE_REMAINING: XiaomiMiioSensorDescription(
        key=ATTR_DUST_FILTER_LIFE_REMAINING,
        name="Dust filter lifetime remaining",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:air-filter",
        state_class=SensorStateClass.MEASUREMENT,
        attributes=("filter_type",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_DUST_FILTER_LIFE_REMAINING_DAYS: XiaomiMiioSensorDescription(
        key=ATTR_DUST_FILTER_LIFE_REMAINING_DAYS,
        name="Dust filter lifetime remaining days",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_UPPER_FILTER_LIFE_REMAINING: XiaomiMiioSensorDescription(
        key=ATTR_UPPER_FILTER_LIFE_REMAINING,
        name="Upper filter lifetime remaining",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:air-filter",
        state_class=SensorStateClass.MEASUREMENT,
        attributes=("filter_type",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_UPPER_FILTER_LIFE_REMAINING_DAYS: XiaomiMiioSensorDescription(
        key=ATTR_UPPER_FILTER_LIFE_REMAINING_DAYS,
        name="Upper filter lifetime remaining days",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_CARBON_DIOXIDE: XiaomiMiioSensorDescription(
        key=ATTR_CARBON_DIOXIDE,
        name="Carbon dioxide",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ATTR_PURIFY_VOLUME: XiaomiMiioSensorDescription(
        key=ATTR_PURIFY_VOLUME,
        name="Purify volume",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_BATTERY: XiaomiMiioSensorDescription(
        key=ATTR_BATTERY,
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}

HUMIDIFIER_MIIO_SENSORS = (
    ATTR_HUMIDITY,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
    ATTR_WATER_LEVEL,
)
HUMIDIFIER_CA1_CB1_SENSORS = (
    ATTR_HUMIDITY,
    ATTR_TEMPERATURE,
    ATTR_MOTOR_SPEED,
    ATTR_USE_TIME,
    ATTR_WATER_LEVEL,
)
HUMIDIFIER_MIOT_SENSORS = (
    ATTR_ACTUAL_SPEED,
    ATTR_HUMIDITY,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
    ATTR_WATER_LEVEL,
)
HUMIDIFIER_MJJSQ_SENSORS = (ATTR_HUMIDITY, ATTR_TEMPERATURE)

PURIFIER_MIIO_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
)
PURIFIER_MIOT_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_PURIFY_VOLUME,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
)
PURIFIER_4_LITE_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_LEFT_TIME,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
)
PURIFIER_4_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_LEFT_TIME,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_PURIFY_VOLUME,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
)
PURIFIER_4_PRO_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_LEFT_TIME,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_PM10,
    ATTR_PURIFY_VOLUME,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
)
PURIFIER_3C_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
)
PURIFIER_ZA1_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_TVOC,
    ATTR_HUMIDITY,
    ATTR_TEMPERATURE,
)
PURIFIER_MA2_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
    ATTR_ILLUMINANCE,
)
PURIFIER_V2_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_PURIFY_VOLUME,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
)
PURIFIER_V3_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_ILLUMINANCE_LUX,
    ATTR_MOTOR2_SPEED,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_PURIFY_VOLUME,
    ATTR_USE_TIME,
)
PURIFIER_PRO_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_ILLUMINANCE_LUX,
    ATTR_MOTOR2_SPEED,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_PURIFY_VOLUME,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
)
PURIFIER_PRO_V7_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_ILLUMINANCE_LUX,
    ATTR_MOTOR2_SPEED,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
)
AIRFRESH_SENSORS = (
    ATTR_CARBON_DIOXIDE,
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_PM25,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
)
AIRFRESH_SENSORS_A1 = (
    ATTR_CARBON_DIOXIDE,
    ATTR_DUST_FILTER_LIFE_REMAINING,
    ATTR_DUST_FILTER_LIFE_REMAINING_DAYS,
    ATTR_PM25_2,
    ATTR_TEMPERATURE,
    ATTR_CONTROL_SPEED,
    ATTR_FAVORITE_SPEED,
)
AIRFRESH_SENSORS_T2017 = (
    ATTR_CARBON_DIOXIDE,
    ATTR_DUST_FILTER_LIFE_REMAINING,
    ATTR_DUST_FILTER_LIFE_REMAINING_DAYS,
    ATTR_UPPER_FILTER_LIFE_REMAINING,
    ATTR_UPPER_FILTER_LIFE_REMAINING_DAYS,
    ATTR_PM25_2,
    ATTR_TEMPERATURE,
    ATTR_CONTROL_SPEED,
    ATTR_FAVORITE_SPEED,
)
FAN_V2_V3_SENSORS = (
    ATTR_BATTERY,
    ATTR_HUMIDITY,
    ATTR_TEMPERATURE,
)

FAN_ZA5_SENSORS = (ATTR_HUMIDITY, ATTR_TEMPERATURE)

MODEL_TO_SENSORS_MAP: dict[str, tuple[str, ...]] = {
    MODEL_AIRFRESH_A1: AIRFRESH_SENSORS_A1,
    MODEL_AIRFRESH_VA2: AIRFRESH_SENSORS,
    MODEL_AIRFRESH_VA4: AIRFRESH_SENSORS,
    MODEL_AIRFRESH_T2017: AIRFRESH_SENSORS_T2017,
    MODEL_AIRHUMIDIFIER_CA1: HUMIDIFIER_CA1_CB1_SENSORS,
    MODEL_AIRHUMIDIFIER_CB1: HUMIDIFIER_CA1_CB1_SENSORS,
    MODEL_AIRPURIFIER_3C: PURIFIER_3C_SENSORS,
    MODEL_AIRPURIFIER_4_LITE_RMA1: PURIFIER_4_LITE_SENSORS,
    MODEL_AIRPURIFIER_4_LITE_RMB1: PURIFIER_4_LITE_SENSORS,
    MODEL_AIRPURIFIER_4: PURIFIER_4_SENSORS,
    MODEL_AIRPURIFIER_4_PRO: PURIFIER_4_PRO_SENSORS,
    MODEL_AIRPURIFIER_PRO: PURIFIER_PRO_SENSORS,
    MODEL_AIRPURIFIER_PRO_V7: PURIFIER_PRO_V7_SENSORS,
    MODEL_AIRPURIFIER_V2: PURIFIER_V2_SENSORS,
    MODEL_AIRPURIFIER_V3: PURIFIER_V3_SENSORS,
    MODEL_AIRPURIFIER_ZA1: PURIFIER_ZA1_SENSORS,
    MODEL_AIRPURIFIER_MA2: PURIFIER_MA2_SENSORS,
    MODEL_FAN_V2: FAN_V2_V3_SENSORS,
    MODEL_FAN_V3: FAN_V2_V3_SENSORS,
    MODEL_FAN_ZA5: FAN_ZA5_SENSORS,
}

VACUUM_SENSORS = {
    f"dnd_{ATTR_DND_START}": XiaomiMiioSensorDescription(
        key=ATTR_DND_START,
        icon="mdi:minus-circle-off",
        name="DnD start",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key=VacuumCoordinatorDataAttributes.dnd_status,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"dnd_{ATTR_DND_END}": XiaomiMiioSensorDescription(
        key=ATTR_DND_END,
        icon="mdi:minus-circle-off",
        name="DnD end",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key=VacuumCoordinatorDataAttributes.dnd_status,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_START}": XiaomiMiioSensorDescription(
        key=ATTR_LAST_CLEAN_START,
        icon="mdi:clock-time-twelve",
        name="Last clean start",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key=VacuumCoordinatorDataAttributes.last_clean_details,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_END}": XiaomiMiioSensorDescription(
        key=ATTR_LAST_CLEAN_END,
        icon="mdi:clock-time-twelve",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key=VacuumCoordinatorDataAttributes.last_clean_details,
        name="Last clean end",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_TIME}": XiaomiMiioSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        key=ATTR_LAST_CLEAN_TIME,
        parent_key=VacuumCoordinatorDataAttributes.last_clean_details,
        name="Last clean duration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_AREA}": XiaomiMiioSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        icon="mdi:texture-box",
        key=ATTR_LAST_CLEAN_AREA,
        parent_key=VacuumCoordinatorDataAttributes.last_clean_details,
        name="Last clean area",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_STATUS_CLEAN_TIME}": XiaomiMiioSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        key=ATTR_STATUS_CLEAN_TIME,
        parent_key=VacuumCoordinatorDataAttributes.status,
        name="Current clean duration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_LAST_CLEAN_AREA}": XiaomiMiioSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        icon="mdi:texture-box",
        key=ATTR_STATUS_CLEAN_AREA,
        parent_key=VacuumCoordinatorDataAttributes.status,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Current clean area",
    ),
    f"clean_history_{ATTR_CLEAN_HISTORY_TOTAL_DURATION}": XiaomiMiioSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-sand",
        key=ATTR_CLEAN_HISTORY_TOTAL_DURATION,
        parent_key=VacuumCoordinatorDataAttributes.clean_history_status,
        name="Total duration",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"clean_history_{ATTR_CLEAN_HISTORY_TOTAL_AREA}": XiaomiMiioSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        icon="mdi:texture-box",
        key=ATTR_CLEAN_HISTORY_TOTAL_AREA,
        parent_key=VacuumCoordinatorDataAttributes.clean_history_status,
        name="Total clean area",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"clean_history_{ATTR_CLEAN_HISTORY_COUNT}": XiaomiMiioSensorDescription(
        native_unit_of_measurement="",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        key=ATTR_CLEAN_HISTORY_COUNT,
        parent_key=VacuumCoordinatorDataAttributes.clean_history_status,
        name="Total clean count",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"clean_history_{ATTR_CLEAN_HISTORY_DUST_COLLECTION_COUNT}": XiaomiMiioSensorDescription(
        native_unit_of_measurement="",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        key=ATTR_CLEAN_HISTORY_DUST_COLLECTION_COUNT,
        parent_key=VacuumCoordinatorDataAttributes.clean_history_status,
        name="Total dust collection count",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_MAIN_BRUSH_LEFT}": XiaomiMiioSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        key=ATTR_CONSUMABLE_STATUS_MAIN_BRUSH_LEFT,
        parent_key=VacuumCoordinatorDataAttributes.consumable_status,
        name="Main brush left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_SIDE_BRUSH_LEFT}": XiaomiMiioSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        key=ATTR_CONSUMABLE_STATUS_SIDE_BRUSH_LEFT,
        parent_key=VacuumCoordinatorDataAttributes.consumable_status,
        name="Side brush left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_FILTER_LEFT}": XiaomiMiioSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.DURATION,
        key=ATTR_CONSUMABLE_STATUS_FILTER_LEFT,
        parent_key=VacuumCoordinatorDataAttributes.consumable_status,
        name="Filter left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_SENSOR_DIRTY_LEFT}": XiaomiMiioSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:eye-outline",
        device_class=SensorDeviceClass.DURATION,
        key=ATTR_CONSUMABLE_STATUS_SENSOR_DIRTY_LEFT,
        parent_key=VacuumCoordinatorDataAttributes.consumable_status,
        name="Sensor dirty left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


def _setup_vacuum_sensors(hass, config_entry, async_add_entities):
    """Set up the Xiaomi vacuum sensors."""
    device = hass.data[DOMAIN][config_entry.entry_id].get(KEY_DEVICE)
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
    entities = []

    for sensor, description in VACUUM_SENSORS.items():
        parent_key_data = getattr(coordinator.data, description.parent_key)
        if getattr(parent_key_data, description.key, None) is None:
            _LOGGER.debug(
                "It seems the %s does not support the %s as the initial value is None",
                config_entry.data[CONF_MODEL],
                description.key,
            )
            continue
        entities.append(
            XiaomiGenericSensor(
                device,
                config_entry,
                f"{sensor}_{config_entry.unique_id}",
                coordinator,
                description,
            )
        )

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Xiaomi sensor from a config entry."""
    entities: list[SensorEntity] = []

    if config_entry.data[CONF_FLOW_TYPE] == CONF_GATEWAY:
        gateway = hass.data[DOMAIN][config_entry.entry_id][CONF_GATEWAY]
        # Gateway illuminance sensor
        if gateway.model not in [
            GATEWAY_MODEL_AC_V1,
            GATEWAY_MODEL_AC_V2,
            GATEWAY_MODEL_AC_V3,
            GATEWAY_MODEL_AQARA,
            GATEWAY_MODEL_EU,
        ]:
            description = SENSOR_TYPES[ATTR_ILLUMINANCE]
            entities.append(
                XiaomiGatewayIlluminanceSensor(
                    gateway, config_entry.title, config_entry.unique_id, description
                )
            )
        # Gateway sub devices
        sub_devices = gateway.devices
        for sub_device in sub_devices.values():
            coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR][
                sub_device.sid
            ]
            for sensor, description in SENSOR_TYPES.items():
                if sensor not in sub_device.status:
                    continue
                entities.append(
                    XiaomiGatewaySensor(
                        coordinator, sub_device, config_entry, description
                    )
                )
    elif config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        host = config_entry.data[CONF_HOST]
        token = config_entry.data[CONF_TOKEN]
        model: str = config_entry.data[CONF_MODEL]

        if model in (MODEL_FAN_ZA1, MODEL_FAN_ZA3, MODEL_FAN_ZA4, MODEL_FAN_P5):
            return

        if model in MODELS_AIR_QUALITY_MONITOR:
            unique_id = config_entry.unique_id
            name = config_entry.title
            _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

            device = AirQualityMonitor(host, token)
            description = SENSOR_TYPES[ATTR_AIR_QUALITY]
            entities.append(
                XiaomiAirQualityMonitor(
                    name, device, config_entry, unique_id, description
                )
            )
        else:
            device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
            sensors: Iterable[str] = []
            if model in MODEL_TO_SENSORS_MAP:
                sensors = MODEL_TO_SENSORS_MAP[model]
            elif model in MODELS_HUMIDIFIER_MIOT:
                sensors = HUMIDIFIER_MIOT_SENSORS
            elif model in MODELS_HUMIDIFIER_MJJSQ:
                sensors = HUMIDIFIER_MJJSQ_SENSORS
            elif model in MODELS_HUMIDIFIER_MIIO:
                sensors = HUMIDIFIER_MIIO_SENSORS
            elif model in MODELS_PURIFIER_MIIO:
                sensors = PURIFIER_MIIO_SENSORS
            elif model in MODELS_PURIFIER_MIOT:
                sensors = PURIFIER_MIOT_SENSORS
            elif (
                model in MODELS_VACUUM
                or model.startswith(ROBOROCK_GENERIC)
                or model.startswith(ROCKROBO_GENERIC)
            ):
                return _setup_vacuum_sensors(hass, config_entry, async_add_entities)

            for sensor, description in SENSOR_TYPES.items():
                if sensor not in sensors:
                    continue
                entities.append(
                    XiaomiGenericSensor(
                        device,
                        config_entry,
                        f"{sensor}_{config_entry.unique_id}",
                        hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
                        description,
                    )
                )

    async_add_entities(entities)


class XiaomiGenericSensor(XiaomiCoordinatedMiioEntity, SensorEntity):
    """Representation of a Xiaomi generic sensor."""

    entity_description: XiaomiMiioSensorDescription

    def __init__(self, device, entry, unique_id, coordinator, description):
        """Initialize the entity."""
        super().__init__(device, entry, unique_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = unique_id
        self._attr_native_value = self._determine_native_value()
        self._attr_extra_state_attributes = self._extract_attributes(coordinator.data)

    @callback
    def _extract_attributes(self, data):
        """Return state attributes with valid values."""
        return {
            attr: value
            for attr in self.entity_description.attributes
            if hasattr(data, attr)
            and (value := self._extract_value_from_attribute(data, attr)) is not None
        }

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        native_value = self._determine_native_value()
        # Sometimes (quite rarely) the device returns None as the sensor value so we
        # check that the value is not None before updating the state.
        if native_value is not None:
            self._attr_native_value = native_value
            self._attr_extra_state_attributes = self._extract_attributes(
                self.coordinator.data
            )
            self.async_write_ha_state()

    def _determine_native_value(self):
        """Determine native value."""
        if self.entity_description.parent_key is not None:
            native_value = self._extract_value_from_attribute(
                getattr(self.coordinator.data, self.entity_description.parent_key),
                self.entity_description.key,
            )
        else:
            native_value = self._extract_value_from_attribute(
                self.coordinator.data, self.entity_description.key
            )

        if (
            self.device_class == SensorDeviceClass.TIMESTAMP
            and native_value is not None
            and (native_datetime := dt_util.parse_datetime(str(native_value)))
            is not None
        ):
            return native_datetime.astimezone(dt_util.UTC)

        return native_value


class XiaomiAirQualityMonitor(XiaomiMiioEntity, SensorEntity):
    """Representation of a Xiaomi Air Quality Monitor."""

    def __init__(self, name, device, entry, unique_id, description):
        """Initialize the entity."""
        super().__init__(name, device, entry, unique_id)

        self._available = None
        self._state = None
        self._state_attrs = {
            ATTR_POWER: None,
            ATTR_BATTERY_LEVEL: None,
            ATTR_CHARGING: None,
            ATTR_DISPLAY_CLOCK: None,
            ATTR_NIGHT_MODE: None,
            ATTR_NIGHT_TIME_BEGIN: None,
            ATTR_NIGHT_TIME_END: None,
            ATTR_SENSOR_STATE: None,
        }
        self.entity_description = description

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    async def async_update(self) -> None:
        """Fetch state from the miio device."""
        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.aqi
            self._state_attrs.update(
                {
                    ATTR_POWER: state.power,
                    ATTR_CHARGING: state.usb_power,
                    ATTR_BATTERY_LEVEL: state.battery,
                    ATTR_DISPLAY_CLOCK: state.display_clock,
                    ATTR_NIGHT_MODE: state.night_mode,
                    ATTR_NIGHT_TIME_BEGIN: state.night_time_begin,
                    ATTR_NIGHT_TIME_END: state.night_time_end,
                    ATTR_SENSOR_STATE: state.sensor_state,
                }
            )

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)


class XiaomiGatewaySensor(XiaomiGatewayDevice, SensorEntity):
    """Representation of a XiaomiGatewaySensor."""

    def __init__(self, coordinator, sub_device, entry, description):
        """Initialize the XiaomiSensor."""
        super().__init__(coordinator, sub_device, entry)
        self._unique_id = f"{sub_device.sid}-{description.key}"
        self._name = f"{description.key} ({sub_device.sid})".capitalize()
        self.entity_description = description

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._sub_device.status[self.entity_description.key]


class XiaomiGatewayIlluminanceSensor(SensorEntity):
    """Representation of the gateway device's illuminance sensor."""

    def __init__(self, gateway_device, gateway_name, gateway_device_id, description):
        """Initialize the entity."""
        self._attr_name = f"{gateway_name} {description.name}"
        self._attr_unique_id = f"{gateway_device_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gateway_device_id)},
        )
        self._gateway = gateway_device
        self.entity_description = description
        self._available = False
        self._state = None

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    async def async_update(self) -> None:
        """Fetch state from the device."""
        try:
            self._state = await self.hass.async_add_executor_job(
                self._gateway.get_illumination
            )
            self._available = True
        except GatewayException as ex:
            if self._available:
                self._available = False
                _LOGGER.error(
                    "Got exception while fetching the gateway illuminance state: %s", ex
                )
