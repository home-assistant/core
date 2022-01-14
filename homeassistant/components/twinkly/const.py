"""Const for Twinkly."""

DOMAIN = "twinkly"

# Keys of the config entry
ENTRY_DATA_ID = "id"
ENTRY_DATA_HOST = "host"
ENTRY_DATA_NAME = "name"
ENTRY_DATA_MODEL = "model"

# Strongly named HA attributes keys
ATTR_HOST = "host"

# Keys of attributes read from the get_device_info
DEV_ID = "uuid"
DEV_NAME = "device_name"
DEV_MODEL = "product_code"
DEV_LED_PROFILE = "led_profile"

DEV_PROFILE_RGB = "RGB"
DEV_PROFILE_RGBW = "RGBW"

DATA_CLIENT = "client"
DATA_DEVICE_INFO = "device_info"

HIDDEN_DEV_VALUES = (
    "code",  # This is the internal status code of the API response
    "copyright",  # We should not display a copyright "LEDWORKS 2018" in the Home-Assistant UI
    "mac",  # Does not report the actual device mac address
)
