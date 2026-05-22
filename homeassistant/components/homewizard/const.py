"""Constants for the Homewizard integration."""

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "homewizard"
ISSUE_BATTERY_MODE_CLOUD_DISABLED = "battery_mode_cloud_disabled"
PLATFORMS = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

LOGGER = logging.getLogger(__package__)

# Platform config.
CONF_PRODUCT_NAME = "product_name"
CONF_PRODUCT_TYPE = "product_type"
CONF_SERIAL = "serial"

UPDATE_INTERVAL = timedelta(seconds=5)
