"""Constants for the MusicCast integration."""
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import config_validation as cv

DOMAIN = "yamaha_musiccast"

BRAND = "Yamaha Corporation"

# Attributes
ATTR_COLOR_PRIMARY = "color_primary"
ATTR_DURATION = "duration"
ATTR_FADE = "fade"
ATTR_IDENTIFIERS = "identifiers"
ATTR_INTENSITY = "intensity"
ATTR_LED_COUNT = "led_count"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MAX_POWER = "max_power"
ATTR_MODEL = "model"
ATTR_ON = "on"
ATTR_PALETTE = "palette"
ATTR_PLAYLIST = "playlist"
ATTR_PRESET = "preset"
ATTR_REVERSE = "reverse"
ATTR_SEGMENT_ID = "segment_id"
ATTR_SOFTWARE_VERSION = "sw_version"
ATTR_SPEED = "speed"
ATTR_TARGET_BRIGHTNESS = "target_brightness"
ATTR_UDP_PORT = "udp_port"

ATTR_MC_LINK = "mc_link"
ATTR_MAIN_SYNC = "main_sync"
ATTR_MC_LINK_SOURCES = [ATTR_MC_LINK, ATTR_MAIN_SYNC]
SERVICE_JOIN = "join"
SERVICE_UNJOIN = "unjoin"
ATTR_MASTER = "master"

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

NULL_GROUP = "00000000000000000000000000000000"

ATTR_MUSICCAST_GROUP = DOMAIN + "_group"
