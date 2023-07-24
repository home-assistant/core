"""Constants for the UniFi Network integration."""

import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)
DOMAIN = "unifi"

PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.IMAGE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

CONF_SITE_ID = "site"

UNIFI_WIRELESS_CLIENTS = "unifi_wireless_clients"

CONF_ALLOW_BANDWIDTH_SENSORS = "allow_bandwidth_sensors"
CONF_ALLOW_UPTIME_SENSORS = "allow_uptime_sensors"
CONF_BLOCK_CLIENT = "block_client"
CONF_DETECTION_TIME = "detection_time"
CONF_DPI_RESTRICTIONS = "dpi_restrictions"
CONF_IGNORE_WIRED_BUG = "ignore_wired_bug"
CONF_TRACK_CLIENTS = "track_clients"
CONF_TRACK_DEVICES = "track_devices"
CONF_TRACK_WIRED_CLIENTS = "track_wired_clients"
CONF_SSID_FILTER = "ssid_filter"

DEFAULT_ALLOW_BANDWIDTH_SENSORS = False
DEFAULT_ALLOW_UPTIME_SENSORS = False
DEFAULT_DPI_RESTRICTIONS = True
DEFAULT_IGNORE_WIRED_BUG = False
DEFAULT_TRACK_CLIENTS = True
DEFAULT_TRACK_DEVICES = True
DEFAULT_TRACK_WIRED_CLIENTS = True
DEFAULT_DETECTION_TIME = 300

ATTR_MANUFACTURER = "Ubiquiti Networks"

BLOCK_SWITCH = "block"
DPI_SWITCH = "dpi"
OUTLET_SWITCH = "outlet"
