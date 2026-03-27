"""Constants for the Grandstream Home integration."""

DOMAIN = "grandstream_home"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_PORT = "port"

# Protocol configuration
CONF_USE_HTTPS = "use_https"
CONF_VERIFY_SSL = "verify_ssl"  # SSL certificate verification

DEFAULT_PORT = 443  # Default HTTPS port for GDS devices
DEFAULT_USERNAME = "gdsha"
DEFAULT_USERNAME_GNS = "admin"

# Device Types
CONF_DEVICE_TYPE = "device_type"
CONF_DEVICE_MODEL = "device_model"  # Original device model (GDS/GSC/GNS)
CONF_PRODUCT_MODEL = (
    "product_model"  # Specific product model (e.g., GDS3725, GDS3727, GSC3560)
)
CONF_FIRMWARE_VERSION = "firmware_version"  # Firmware version from discovery
DEVICE_TYPE_GDS = "GDS"
DEVICE_TYPE_GSC = "GSC"
DEVICE_TYPE_GNS_NAS = "GNS"

# SIP registration status mapping
SIP_STATUS_MAP = {
    0: "unregistered",
    1: "registered",
}

# Default Port Settings
DEFAULT_HTTP_PORT = 5000
DEFAULT_HTTPS_PORT = 5001

# Version information
INTEGRATION_VERSION = "1.0.0"

# Coordinator settings
COORDINATOR_UPDATE_INTERVAL = 10  # seconds - How often to poll device status
COORDINATOR_ERROR_THRESHOLD = 3  # Max consecutive errors before marking unavailable
