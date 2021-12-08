"""Constants for the Homewizard integration."""

# Set up.
from datetime import timedelta

DOMAIN = "homewizard"
COORDINATOR = "coordinator"
PLATFORMS = ["sensor"]

# Platform config.
CONF_SERIAL = "serial"
CONF_PRODUCT_NAME = "product_name"
CONF_PRODUCT_TYPE = "product_type"
CONF_DEVICE = "device"
CONF_DATA = "data"

UPDATE_INTERVAL = timedelta(seconds=5)
