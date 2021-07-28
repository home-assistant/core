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
ATTR_MC_LINK = "mc_link"
ATTR_MAIN_SYNC = "main_sync"
ATTR_MC_LINK_SOURCES = [ATTR_MC_LINK, ATTR_MAIN_SYNC]

DEFAULT_ZONE = "main"
HA_REPEAT_MODE_TO_MC_MAPPING = {
    REPEAT_MODE_OFF: "off",
    REPEAT_MODE_ONE: "one",
    REPEAT_MODE_ALL: "all",
}

NULL_GROUP = "00000000000000000000000000000000"

INTERVAL_SECONDS = "interval_seconds"

MC_REPEAT_MODE_TO_HA_MAPPING = {
    val: key for key, val in HA_REPEAT_MODE_TO_MC_MAPPING.items()
}
