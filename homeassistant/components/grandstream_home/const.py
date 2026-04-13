"""Constants for the Grandstream Home integration."""

from grandstream_home_api.const import (
    DEFAULT_HTTP_PORT,
    DEFAULT_HTTPS_PORT,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DEFAULT_USERNAME_GNS,
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
    DEVICE_TYPE_GSC,
)

DOMAIN = "grandstream_home"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_PORT = "port"
CONF_VERIFY_SSL = "verify_ssl"
CONF_DEVICE_TYPE = "device_type"
CONF_DEVICE_MODEL = "device_model"
CONF_PRODUCT_MODEL = "product_model"
CONF_FIRMWARE_VERSION = "firmware_version"

# Coordinator settings
COORDINATOR_UPDATE_INTERVAL = 10
COORDINATOR_ERROR_THRESHOLD = 3

__all__ = [
    "CONF_DEVICE_MODEL",
    "CONF_DEVICE_TYPE",
    "CONF_FIRMWARE_VERSION",
    "CONF_PASSWORD",
    "CONF_PORT",
    "CONF_PRODUCT_MODEL",
    "CONF_USERNAME",
    "CONF_VERIFY_SSL",
    "COORDINATOR_ERROR_THRESHOLD",
    "COORDINATOR_UPDATE_INTERVAL",
    "DEFAULT_HTTPS_PORT",
    "DEFAULT_HTTP_PORT",
    "DEFAULT_PORT",
    "DEFAULT_USERNAME",
    "DEFAULT_USERNAME_GNS",
    "DEVICE_TYPE_GDS",
    "DEVICE_TYPE_GNS_NAS",
    "DEVICE_TYPE_GSC",
    "DOMAIN",
]
