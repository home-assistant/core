"""Constants for Roborock."""
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.size import Size

from homeassistant.const import Platform

DOMAIN = "roborock"
CONF_ENTRY_CODE = "code"
CONF_BASE_URL = "base_url"
CONF_USER_DATA = "user_data"

# domain options
CONF_INCLUDE_SHARED = "include_shared"
DEFAULT_INCLUDE_SHARED = True

# Option Flow steps
SIZES = "sizes"
DRAWABLES = "drawables"
MAPS = "maps"

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

DEFAULT_SIZES = {
    Size.VACUUM_RADIUS: 6,
    Size.PATH_WIDTH: 1,
    Size.IGNORED_OBSTACLE_RADIUS: 3,
    Size.IGNORED_OBSTACLE_WITH_PHOTO_RADIUS: 3,
    Size.OBSTACLE_RADIUS: 3,
    Size.OBSTACLE_WITH_PHOTO_RADIUS: 3,
    Size.CHARGER_RADIUS: 6,
    Size.MOP_PATH_WIDTH: 1,
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
