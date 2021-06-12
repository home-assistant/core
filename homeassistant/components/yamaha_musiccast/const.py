"""Constants for the MusicCast integration."""
import voluptuous as vol

from homeassistant.components.media_player.const import (
    REPEAT_MODE_ALL,
    REPEAT_MODE_OFF,
    REPEAT_MODE_ONE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import config_validation as cv

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
ATTR_MASTER = "master"
SERVICE_JOIN = "join"
SERVICE_UNJOIN = "unjoin"

UNJOIN_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    }
)

JOIN_SERVICE_SCHEMA = UNJOIN_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_MASTER): cv.entity_id,
    }
)


DEFAULT_ZONE = "main"
HA_REPEAT_MODE_TO_MC_MAPPING = {
    REPEAT_MODE_OFF: "off",
    REPEAT_MODE_ONE: "one",
    REPEAT_MODE_ALL: "all",
}

NULL_GROUP = "00000000000000000000000000000000"

ATTR_MUSICCAST_GROUP = DOMAIN + "_group"

INTERVAL_SECONDS = "interval_seconds"

MC_REPEAT_MODE_TO_HA_MAPPING = {
    val: key for key, val in HA_REPEAT_MODE_TO_MC_MAPPING.items()
}
