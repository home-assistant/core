"""Constants for the Google Wifi integration."""
from __future__ import annotations

from dataclasses import dataclass
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import UnitOfTime

DOMAIN = "google_wifi"

# Attribute Keys
ATTR_CURRENT_VERSION = "current_version"
ATTR_LAST_RESTART = "last_restart"
ATTR_LOCAL_IP = "local_ip"
ATTR_NEW_VERSION = "new_version"
ATTR_STATUS = "status"
ATTR_UPTIME = "uptime"
ATTR_MODEL = "model"
ATTR_GROUP_ROLE = "group_role"

@dataclass(frozen=True, kw_only=True)
class GoogleWifiSensorEntityDescription(SensorEntityDescription):
    """Describes GoogleWifi sensor entity."""
    primary_key: str
    sensor_key: str

# Define all sensors in one tuple to be imported by sensor.py
SENSOR_TYPES: tuple[GoogleWifiSensorEntityDescription, ...] = (
    GoogleWifiSensorEntityDescription(
        key=ATTR_CURRENT_VERSION,
        primary_key="software",
        sensor_key="softwareVersion",
        icon="mdi:checkbox-marked-circle-outline",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_NEW_VERSION,
        primary_key="software",
        sensor_key="updateNewVersion",
        icon="mdi:update",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_UPTIME,
        primary_key="system",
        sensor_key="uptime",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:timelapse",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LAST_RESTART,
        primary_key="system",
        sensor_key="uptime",
        icon="mdi:restart",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LOCAL_IP,
        primary_key="wan",
        sensor_key="localIpAddress",
        icon="mdi:access-point-network",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_STATUS,
        primary_key="wan",
        sensor_key="online",
        icon="mdi:google",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_MODEL,
        primary_key="system",
        sensor_key="modelId",
        icon="mdi:router-network-wireless",
        entity_category="diagnostic"
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_GROUP_ROLE,
        primary_key="system",
        sensor_key="groupRole",
        icon="mdi:family-tree",
    ),
)
