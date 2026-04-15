"""Constants for the Grandstream Home integration."""

# Fixed username for Grandstream devices
DEFAULT_USERNAME = "gdsha"

# Default port
DEFAULT_PORT = 443

DOMAIN = "grandstream_home"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_PORT = "port"
CONF_VERIFY_SSL = "verify_ssl"
CONF_DEVICE_MODEL = "device_model"
CONF_PRODUCT_MODEL = "product_model"
CONF_FIRMWARE_VERSION = "firmware_version"

# Coordinator settings
COORDINATOR_UPDATE_INTERVAL = 10
COORDINATOR_ERROR_THRESHOLD = 3
