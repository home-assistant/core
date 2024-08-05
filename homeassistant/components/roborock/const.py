"""Constants for Roborock."""

from vacuum_map_parser_base.config.drawable import Drawable

from homeassistant.const import Platform

DOMAIN = "roborock"
CONF_ENTRY_CODE = "code"
CONF_BASE_URL = "base_url"
CONF_USER_DATA = "user_data"

# Option Flow steps
DRAWABLES = "drawables"

DEFAULT_DRAWABLES = {
    Drawable.CHARGER: True,
    Drawable.CLEANED_AREA: False,
    Drawable.GOTO_PATH: False,
    Drawable.IGNORED_OBSTACLES: False,
    Drawable.IGNORED_OBSTACLES_WITH_PHOTO: False,
    Drawable.MOP_PATH: False,
    Drawable.NO_CARPET_AREAS: False,
    Drawable.NO_GO_AREAS: False,
    Drawable.NO_MOPPING_AREAS: False,
    Drawable.OBSTACLES: False,
    Drawable.OBSTACLES_WITH_PHOTO: False,
    Drawable.PATH: True,
    Drawable.PREDICTED_PATH: False,
    Drawable.VACUUM_POSITION: True,
    Drawable.VIRTUAL_WALLS: False,
    Drawable.ZONES: False,
}

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


IMAGE_CACHE_INTERVAL = 90

MAP_SLEEP = 3

GET_MAPS_SERVICE_NAME = "get_maps"
