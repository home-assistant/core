"""Constants for the UniFi component."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "unifi"

CONTROLLER_ID = "{host}-{site}"

CONF_CONTROLLER = "controller"
CONF_SITE_ID = "site"

UNIFI_CONFIG = "unifi_config"

CONF_BLOCK_CLIENT = "block_client"
CONF_DETECTION_TIME = "detection_time"
CONF_SSID_FILTER = "ssid_filter"

ATTR_MANUFACTURER = "Ubiquiti Networks"
