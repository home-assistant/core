"""Const for Twinkly."""

DOMAIN = "twinkly"

# Keys of the config entry
CONF_ENTRY_ID = "id"
CONF_ENTRY_HOST = "host"
CONF_ENTRY_NAME = "name"
CONF_ENTRY_MODEL = "model"

# Strongly named HA attributes keys
ATTR_HOST = "host"

# Keys of attributes read from the get_device_info
DEV_ID = "uuid"
DEV_NAME = "device_name"
DEV_MODEL = "product_code"

HIDDEN_DEV_VALUES = (
    "code",  # This is the internal status code of the API response
    "copyright",  # We should not display a copyright "LEDWORKS 2018" in the Home-Assistant UI
    "mac",  # Does not report the actual device mac address
)
