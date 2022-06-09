"""Constants for the MusicCast integration."""

from aiomusiccast.capabilities import EntityType

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_TRACK,
    REPEAT_MODE_ALL,
    REPEAT_MODE_OFF,
    REPEAT_MODE_ONE,
)
from homeassistant.helpers.entity import EntityCategory

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


MC_REPEAT_MODE_TO_HA_MAPPING = {
    val: key for key, val in HA_REPEAT_MODE_TO_MC_MAPPING.items()
}

MEDIA_CLASS_MAPPING = {
    "track": MEDIA_CLASS_TRACK,
    "directory": MEDIA_CLASS_DIRECTORY,
    "categories": MEDIA_CLASS_DIRECTORY,
}

ENTITY_CATEGORY_MAPPING = {
    EntityType.CONFIG: EntityCategory.CONFIG,
    EntityType.REGULAR: None,
    EntityType.DIAGNOSTIC: EntityCategory.DIAGNOSTIC,
}

DEVICE_CLASS_MAPPING = {
    "DIMMER": "yamaha_musiccast__dimmer",
    "zone_SLEEP": "yamaha_musiccast__zone_sleep",
    "zone_TONE_CONTROL_mode": "yamaha_musiccast__zone_tone_control_mode",
    "zone_SURR_DECODER_TYPE": "yamaha_musiccast__zone_surr_decoder_type",
    "zone_EQUALIZER_mode": "yamaha_musiccast__zone_equalizer_mode",
    "zone_LINK_AUDIO_QUALITY": "yamaha_musiccast__zone_link_audio_quality",
    "zone_LINK_CONTROL": "yamaha_musiccast__zone_link_control",
    "zone_LINK_AUDIO_DELAY": "yamaha_musiccast__zone_link_audio_delay",
}
