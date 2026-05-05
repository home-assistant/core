from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from homeassistant.components.sensor import SensorEntityDescription

DOMAIN = "google_wifi"

# Attribute Keys
ATTR_CURRENT_VERSION = "current_version"
ATTR_LAST_RESTART = "last_restart"
ATTR_LOCAL_IP = "local_ip"
ATTR_NEW_VERSION = "new_version"
ATTR_STATUS = "status"
ATTR_UPTIME = "uptime"

# API Constants
ENDPOINT = "/api/v1/status"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

@dataclass(frozen=True, kw_only=True)
class GoogleWifiSensorEntityDescription(SensorEntityDescription):
    """Describes Google Wifi sensor entity."""
    primary_key: str
    sensor_key: str

SENSOR_TYPES: tuple[GoogleWifiSensorEntityDescription, ...] = (
    GoogleWifiSensorEntityDescription(
        key=ATTR_CURRENT_VERSION,
        name="Software Version",
        primary_key="software",
        sensor_key="softwareVersion",
        icon="mdi:checkbox-marked-circle-outline",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_NEW_VERSION,
        name="New Version",
        primary_key="software",
        sensor_key="updateNewVersion",
        icon="mdi:update",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_UPTIME,
        name="Uptime",
        primary_key="system",
        sensor_key="uptime",
        native_unit_of_measurement="d",
        icon="mdi:timelapse",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LAST_RESTART,
        name="Last Restart",
        primary_key="system",
        sensor_key="uptime",
        icon="mdi:restart",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LOCAL_IP,
        name="Local IP",
        primary_key="wan",
        sensor_key="localIpAddress",
        icon="mdi:access-point-network",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_STATUS,
        name="Status",
        primary_key="wan",
        sensor_key="online",
        icon="mdi:google",
    ),
)