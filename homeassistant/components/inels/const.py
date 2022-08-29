"""Constants for the iNels integration."""
import logging

from homeassistant.const import Platform

DOMAIN = "inels"

BROKER_CONFIG = "inels_mqtt_broker_config"
BROKER = "inels_mqtt_broker"
COORDINATOR_LIST = "coordinator_list"

CONF_DISCOVERY_PREFIX = "discovery_prefix"

TITLE = "iNELS"
DESCRIPTION = ""
INELS_VERSION = 1
LOGGER = logging.getLogger(__package__)

ICON_TEMPERATURE = "mdi:thermometer"
ICON_BATTERY = "mdi:battery-50"
ICON_SWITCH = "mdi:power-socket-eu"
ICON_LIGHT = "mdi:lightbulb"
ICON_SHUTTER_CLOSED = "mdi:window-shutter"
ICON_SHUTTER_OPEN = "mdi:window-shutter-open"

ICONS = {
    Platform.SWITCH: ICON_SWITCH,
    Platform.SENSOR: ICON_TEMPERATURE,
}

MANUAL_SETUP = "manual"
