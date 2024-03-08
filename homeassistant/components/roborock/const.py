"""Constants for Roborock."""
from vacuum_map_parser_base.config.drawable import Drawable

from homeassistant.const import Platform

DOMAIN = "roborock"
CONF_ENTRY_CODE = "code"
CONF_BASE_URL = "base_url"
CONF_USER_DATA = "user_data"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.IMAGE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
    Platform.VACUUM,
]

IMAGE_DRAWABLES: list[Drawable] = [
    Drawable.PATH,
    Drawable.CHARGER,
    Drawable.VACUUM_POSITION,
]

IMAGE_CACHE_INTERVAL = 90

MAP_SLEEP = 3
