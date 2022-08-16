"""Constants for the SRP Energy integration."""
from datetime import timedelta
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_DOLLAR, ENERGY_KILO_WATT_HOUR
import homeassistant.util.dt as dt_util

DOMAIN = "srp_energy"
DEFAULT_NAME = "Home"
CONF_IS_TOU = "is_tou"

ATTRIBUTION = "Data provided by SRP Energy"
PHOENIX_TIME_ZONE = dt_util.get_time_zone("America/Phoenix")
TIME_DELTA_BETWEEN_API_UPDATES = timedelta(hours=8)
TIME_DELTA_BETWEEN_UPDATES = timedelta(minutes=30)

DEVICE_CONFIG_URL = "https://www.srpnet.com/"
DEVICE_MANUFACTURER = "srpnet.com"
DEVICE_MODEL = "Service Api"
DEVICE_NAME_ENERGY = "Energy consumption"
DEVICE_NAME_PRICE = "Energy consumption price"

DATA_SUMMARY_KEY_DATETIME: Final = "datetime"
DATA_SUMMARY_KEY_DAY: Final = "day"
DATA_SUMMARY_KEY_HOUR: Final = "hour"
DATA_SUMMARY_KEY_DATE: Final = "iso_date"
DATA_SUMMARY_KEY_VALUE: Final = "value"

HOURLY_KEY_DATE_FORMAT = "%Y-%m-%dT%H:%M:00%z"
DAILY_KEY_DATE_FORMAT = "%Y-%m-%dT00:00:00%z"
FRIENDLY_DAY_FORMAT = "%a, %b %d"
FRIENDLY_HOUR_FORMAT = "%H:%M %p"

AGGRAGATE_ENTITY_KEYS = [
    "hourly_energy_usage_past_48hr",
    "hourly_energy_usage_price_past_48hr",
    "daily_energy_usage_past_2weeks",
    "daily_energy_usage_price_past_2weeks",
]

SENSOR_ENTITIES = [
    (
        SensorEntityDescription(
            key="energy_usage_this_month",
            name="This month",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        DEVICE_NAME_ENERGY,
    ),
    (
        SensorEntityDescription(
            key="energy_usage_this_month_1_day_ago",
            name="This month one day ago",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        DEVICE_NAME_ENERGY,
    ),
    (
        SensorEntityDescription(
            key="energy_usage_this_day",
            name="This day",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        DEVICE_NAME_ENERGY,
    ),
    (
        SensorEntityDescription(
            key="energy_usage_this_day_1_day_ago",
            name="This day one day ago",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        DEVICE_NAME_ENERGY,
    ),
    (
        SensorEntityDescription(
            key="energy_usage_price_this_month",
            name="This month",
            native_unit_of_measurement=CURRENCY_DOLLAR,
            device_class=SensorDeviceClass.MONETARY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        DEVICE_NAME_PRICE,
    ),
    (
        SensorEntityDescription(
            key="energy_usage_price_this_month_1_day_ago",
            name="This month one day ago",
            native_unit_of_measurement=CURRENCY_DOLLAR,
            device_class=SensorDeviceClass.MONETARY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        DEVICE_NAME_PRICE,
    ),
    (
        SensorEntityDescription(
            key="energy_usage_price_this_day",
            name="This day",
            native_unit_of_measurement=CURRENCY_DOLLAR,
            device_class=SensorDeviceClass.MONETARY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        DEVICE_NAME_PRICE,
    ),
    (
        SensorEntityDescription(
            key="energy_usage_price_this_day_1_day_ago",
            name="This day one day ago",
            native_unit_of_measurement=CURRENCY_DOLLAR,
            device_class=SensorDeviceClass.MONETARY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        DEVICE_NAME_PRICE,
    ),
    (
        SensorEntityDescription(
            key="hourly_energy_usage_past_48hr",
            name="past 48hrs hourly",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        DEVICE_NAME_ENERGY,
    ),
    (
        SensorEntityDescription(
            key="hourly_energy_usage_price_past_48hr",
            name="past 48hrs hourly",
            native_unit_of_measurement=CURRENCY_DOLLAR,
            device_class=SensorDeviceClass.MONETARY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        DEVICE_NAME_PRICE,
    ),
    (
        SensorEntityDescription(
            key="daily_energy_usage_past_2weeks",
            name="past 2 weeks daily",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        DEVICE_NAME_ENERGY,
    ),
    (
        SensorEntityDescription(
            key="daily_energy_usage_price_past_2weeks",
            name="past 2 weeks daily",
            native_unit_of_measurement=CURRENCY_DOLLAR,
            device_class=SensorDeviceClass.MONETARY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        DEVICE_NAME_PRICE,
    ),
]
