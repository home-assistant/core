"""Constants for Immich Frames."""

from homeassistant.const import CONF_MODE, CONF_SOURCE

__all__ = ("CONF_MODE", "CONF_SOURCE")

DOMAIN = "immich_frames"
CONF_IMMICH_ENTRY_ID = "immich_entry_id"
CONF_FRAME_NAME = "frame_name"
CONF_FRAME_ID = "frame_id"
CONF_ALBUM_IDS = "album_ids"
CONF_SMART_QUERY = "smart_query"
CONF_ORIENTATION = "orientation"
CONF_TIME_RANGE = "time_range"
CONF_PAIR_WINDOW = "pair_window_days"
CONF_SCREEN_SHAPE = "screen_shape"
CONF_PHOTO_FIT = "photo_fit"
CONF_INTERVAL = "interval"
CONF_MEMORY_WINDOW = "memory_window_days"
CONF_FALLBACK = "fallback_to_all"

SOURCE_ALL = "all"
SOURCE_ALBUM = "album"
SOURCE_SMART = "smart"
SOURCE_MEMORIES = "memories"

MODE_SINGLE = "single"
MODE_PAIRS = "pairs"
MODE_PAIRS_ONLY = "pairs_only"

ORIENTATION_ANY = "any"
ORIENTATION_PORTRAIT = "portrait"
ORIENTATION_LANDSCAPE = "landscape"
ORIENTATION_SQUARE = "square"

PHOTO_FIT_CROP = "crop"
PHOTO_FIT_FULL = "show_full"

SCREEN_SIZES = {
    "landscape": (1280, 800),
    "portrait": (800, 1280),
    "square": (720, 720),
}
DEFAULT_SCREEN_SHAPE = "landscape"
DEFAULT_PHOTO_FIT = PHOTO_FIT_FULL
DEFAULT_INTERVAL = 30
DEFAULT_PAIR_WINDOW = 2
DEFAULT_TIME_RANGE = "all_time"
DEFAULT_SOURCE = SOURCE_ALL
DEFAULT_MODE = MODE_SINGLE
DEFAULT_ORIENTATION = ORIENTATION_ANY
DEFAULT_MEMORY_WINDOW = 2

TIME_RANGE_MONTHS = {
    "all_time": 0,
    "1_month": 1,
    "3_months": 3,
    "6_months": 6,
    "1_year": 12,
    "2_years": 24,
    "3_years": 36,
    "4_years": 48,
    "5_years": 60,
    "10_years": 120,
}

SOURCE_OPTIONS = (SOURCE_ALL, SOURCE_ALBUM, SOURCE_MEMORIES, SOURCE_SMART)
ORIENTATION_OPTIONS = (
    ORIENTATION_ANY,
    ORIENTATION_PORTRAIT,
    ORIENTATION_LANDSCAPE,
    ORIENTATION_SQUARE,
)
MODE_OPTIONS = (MODE_SINGLE, MODE_PAIRS, MODE_PAIRS_ONLY)


def screen_shape(value: str | None) -> str:
    """Return a supported screen shape."""
    return value if value in SCREEN_SIZES else DEFAULT_SCREEN_SHAPE


def photo_fit(value: str | None) -> str:
    """Return a supported photo fit mode."""
    return value if value in (PHOTO_FIT_CROP, PHOTO_FIT_FULL) else DEFAULT_PHOTO_FIT
