"""Constants for the solarman integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "solarman"
DEFAULT_PORT = 8080
UPDATE_INTERVAL = timedelta(seconds=30)
PLATFORMS = [
    Platform.SENSOR,
]

CONF_SERIAL = "serial"
CONF_SN = "sn"
CONF_FW_VERSION = "fw_version"
CONF_FW = "fw"
CONF_PRODUCT_TYPE = "product_type"
