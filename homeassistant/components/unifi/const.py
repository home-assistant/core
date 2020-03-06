"""Constants for the UniFi component."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "unifi"

CONTROLLER_ID = "{host}-{site}"

CONF_CONTROLLER = "controller"
CONF_SITE_ID = "site"

UNIFI_CONFIG = "unifi_config"
UNIFI_WIRELESS_CLIENTS = "unifi_wireless_clients"

CONF_ALLOW_BANDWIDTH_SENSORS = "allow_bandwidth_sensors"
CONF_BLOCK_CLIENT = "block_client"
CONF_DETECTION_TIME = "detection_time"
CONF_TRACK_CLIENTS = "track_clients"
CONF_TRACK_DEVICES = "track_devices"
CONF_TRACK_WIRED_CLIENTS = "track_wired_clients"
CONF_SSID_FILTER = "ssid_filter"

CONF_DONT_TRACK_CLIENTS = "dont_track_clients"
CONF_DONT_TRACK_DEVICES = "dont_track_devices"
CONF_DONT_TRACK_WIRED_CLIENTS = "dont_track_wired_clients"

DEFAULT_ALLOW_BANDWIDTH_SENSORS = False
DEFAULT_TRACK_CLIENTS = True
DEFAULT_TRACK_DEVICES = True
DEFAULT_TRACK_WIRED_CLIENTS = True
DEFAULT_DETECTION_TIME = 300

ATTR_MANUFACTURER = "Ubiquiti Networks"
