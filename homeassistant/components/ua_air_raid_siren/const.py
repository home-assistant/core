"""Consts for the OpenWeatherMap."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.const import Platform

DOMAIN = "ua_air_raid_siren"
DEFAULT_NAME = "Ukraine Air Raid Siren"
DEFAULT_LANGUAGE = "en"
ATTRIBUTION = "Data provided by Ukraine Alarm"
MANUFACTURER = "Ukraine Alarm"
CONF_LANGUAGE = "language"
CONFIG_FLOW_VERSION = 2
ENTRY_NAME = "name"
ENTRY_WEATHER_COORDINATOR = "weather_coordinator"
ALERT_TYPE_UNKNOWN = "UNKNOWN"
ALERT_TYPE_AIR = "AIR"
ALERT_TYPE_ARTILLERY = "URBAN_ARTILLERY"
ALERT_TYPE_URBAN_FIGHTS = "URBAN_FIGHTS"
UPDATE_LISTENER = "update_listener"
PLATFORMS = [Platform.BINARY_SENSOR]

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=ALERT_TYPE_UNKNOWN,
        name="Unknown",
        device_class=BinarySensorDeviceClass.SAFETY,
        # icon
    ),
    BinarySensorEntityDescription(
        key=ALERT_TYPE_AIR,
        name="Air",
        device_class=BinarySensorDeviceClass.SAFETY,
        # icon
    ),
    BinarySensorEntityDescription(
        key=ALERT_TYPE_URBAN_FIGHTS,
        name="Urban Fights",
        device_class=BinarySensorDeviceClass.SAFETY,
        # icon
    ),
    BinarySensorEntityDescription(
        key=ALERT_TYPE_ARTILLERY,
        name="Artillery",
        device_class=BinarySensorDeviceClass.SAFETY,
        # icon
    ),
)
