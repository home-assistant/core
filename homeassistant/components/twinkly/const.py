"""Const for Twinkly."""

DOMAIN = "twinkly"

# Strongly named HA attributes keys
ATTR_HOST = "host"
ATTR_VERSION = "version"

# Keys of attributes read from the get_device_info
DEV_ID = "uuid"
DEV_NAME = "device_name"
DEV_MODEL = "product_code"
DEV_LED_PROFILE = "led_profile"

DEV_PROFILE_RGB = "RGB"
DEV_PROFILE_RGBW = "RGBW"

# Minimum version required to support effects
MIN_EFFECT_VERSION = "2.7.1"

# ttls defaults to a 3 second total timeout, which covers connection setup as
# well as the response. Devices poll every 30 seconds and their radio is idle
# in between, so the first request of a cycle has to wake it inside that
# budget - and frequently does not. See https://github.com/home-assistant/core/issues/160154
DEVICE_TIMEOUT = 10
