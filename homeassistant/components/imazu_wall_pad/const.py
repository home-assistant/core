"""Constants for the Imazu Wall Pad integration."""

from homeassistant.const import Platform

DOMAIN = "imazu_wall_pad"
BRAND_NAME = "imazu"
MANUFACTURER = "Hyundai HT"
MODEL = "WP-IMAZU"
SW_VERSION = "1.0"

DEFAULT_PORT = 8899

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SWITCH,
]
PACKET = "packet"

ATTR_DEVICE = "device"
ATTR_ROOM_ID = "room_id"
ATTR_SUB_ID = "sub_id"
