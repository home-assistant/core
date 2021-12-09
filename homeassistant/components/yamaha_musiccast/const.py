"""Constants for the MusicCast integration."""

from aiomusiccast.capabilities import EntityType

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_TRACK,
    REPEAT_MODE_ALL,
    REPEAT_MODE_OFF,
    REPEAT_MODE_ONE,
)
from homeassistant.const import (
    ENTITY_CATEGORY_CONFIG,
    ENTITY_CATEGORY_DIAGNOSTIC,
    ENTITY_CATEGORY_SYSTEM,
)

DOMAIN = "yamaha_musiccast"

BRAND = "Yamaha Corporation"

# Attributes
ATTR_PLAYLIST = "playlist"
ATTR_PRESET = "preset"
ATTR_MC_LINK = "mc_link"
ATTR_MAIN_SYNC = "main_sync"
ATTR_MC_LINK_SOURCES = [ATTR_MC_LINK, ATTR_MAIN_SYNC]

CONF_UPNP_DESC = "upnp_description"
CONF_SERIAL = "serial"

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

MEDIA_CLASS_MAPPING = {
    "track": MEDIA_CLASS_TRACK,
    "directory": MEDIA_CLASS_DIRECTORY,
    "categories": MEDIA_CLASS_DIRECTORY,
}

ENTITY_CATEGORY_MAPPING = {
    EntityType.CONFIG: ENTITY_CATEGORY_CONFIG,
    EntityType.REGULAR: None,
    EntityType.DIAGNOSTIC: ENTITY_CATEGORY_DIAGNOSTIC,
    EntityType.SYSTEM: ENTITY_CATEGORY_SYSTEM,
}
