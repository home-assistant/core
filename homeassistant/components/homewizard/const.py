"""Constants for the Homewizard integration."""

# Set up.
from datetime import timedelta

DOMAIN = "homewizard"
COORDINATOR = "coordinator"
MANUFACTURER_NAME = "HomeWizard"
PLATFORMS = ["sensor"]

# Platform config.
CONF_SERIAL = "serial"
CONF_PRODUCT_NAME = "product_name"
CONF_PRODUCT_TYPE = "product_type"
CONF_DEVICE = "device"
CONF_API = "api"
CONF_MODEL = "model"
CONF_SW_VERSION = "sw_ver"
CONF_DATA = "data"

UPDATE_INTERVAL = timedelta(seconds=5)

# Default values.
DEFAULT_STR_VALUE = "undefined"
DEVICE_DEFAULT_NAME = "P1 Meter"

# Device models
MODEL_P1 = "HWE-P1"
MODEL_KWH_1 = "SDM230-wifi"
MODEL_KWH_3 = "SDM630-wifi"
