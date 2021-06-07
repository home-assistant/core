"""Constants for the MusicCast integration."""
from homeassistant.components.media_player.const import (
    REPEAT_MODE_ALL,
    REPEAT_MODE_OFF,
    REPEAT_MODE_ONE,
)

DOMAIN = "yamaha_musiccast"

BRAND = "Yamaha Corporation"

# Attributes
ATTR_IDENTIFIERS = "identifiers"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"
ATTR_PLAYLIST = "playlist"
ATTR_PRESET = "preset"
ATTR_SOFTWARE_VERSION = "sw_version"

DEFAULT_ZONE = "main"
REPEAT_MODE_MAPPING = {
    REPEAT_MODE_OFF: "off",
    REPEAT_MODE_ONE: "one",
    REPEAT_MODE_ALL: "all",
}
