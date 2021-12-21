"""The Flume component."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform

DOMAIN = "flume"

PLATFORMS = [Platform.SENSOR]

DEFAULT_NAME = "Flume Sensor"

FLUME_TYPE_SENSOR = 2
FLUME_QUERIES_SENSOR: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="current_interval",
        name="Current",
        native_unit_of_measurement="gal/m",
    ),
    SensorEntityDescription(
        key="month_to_date",
        name="Current Month",
        native_unit_of_measurement="gal",
    ),
    SensorEntityDescription(
        key="week_to_date",
        name="Current Week",
        native_unit_of_measurement="gal",
    ),
    SensorEntityDescription(
        key="today",
        name="Current Day",
        native_unit_of_measurement="gal",
    ),
    SensorEntityDescription(
        key="last_60_min",
        name="60 Minutes",
        native_unit_of_measurement="gal/h",
    ),
    SensorEntityDescription(
        key="last_24_hrs",
        name="24 Hours",
        native_unit_of_measurement="gal/d",
    ),
    SensorEntityDescription(
        key="last_30_days",
        name="30 Days",
        native_unit_of_measurement="gal/mo",
    ),
)

FLUME_AUTH = "flume_auth"
FLUME_HTTP_SESSION = "http_session"
FLUME_DEVICES = "devices"


CONF_TOKEN_FILE = "token_filename"
BASE_TOKEN_FILENAME = "FLUME_TOKEN_FILE"


KEY_DEVICE_TYPE = "type"
KEY_DEVICE_ID = "id"
KEY_DEVICE_LOCATION = "location"
KEY_DEVICE_LOCATION_NAME = "name"
KEY_DEVICE_LOCATION_TIMEZONE = "tz"
