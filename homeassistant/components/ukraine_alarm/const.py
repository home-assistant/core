"""Consts for the Ukraine Alarm."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.const import Platform

DOMAIN = "ukraine_alarm"
DEFAULT_NAME = "Ukraine Alarm"
ATTRIBUTION = "Data provided by Ukraine Alarm"
MANUFACTURER = "Ukraine Alarm"
ALERT_TYPE_UNKNOWN = "UNKNOWN"
ALERT_TYPE_AIR = "AIR"
ALERT_TYPE_ARTILLERY = "ARTILLERY"
ALERT_TYPE_URBAN_FIGHTS = "URBAN_FIGHTS"
ALERT_TYPES = {
    ALERT_TYPE_UNKNOWN,
    ALERT_TYPE_AIR,
    ALERT_TYPE_ARTILLERY,
    ALERT_TYPE_URBAN_FIGHTS,
}
PLATFORMS = [Platform.BINARY_SENSOR]

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=ALERT_TYPE_UNKNOWN,
        name="Unknown",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    BinarySensorEntityDescription(
        key=ALERT_TYPE_AIR,
        name="Air",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:cloud",
    ),
    BinarySensorEntityDescription(
        key=ALERT_TYPE_URBAN_FIGHTS,
        name="Urban Fights",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:pistol",
    ),
    BinarySensorEntityDescription(
        key=ALERT_TYPE_ARTILLERY,
        name="Artillery",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
)
