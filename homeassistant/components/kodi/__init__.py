"""The kodi component."""

import asyncio
import logging

from homeassistant.const import CONF_PLATFORM
from homeassistant.components.kodi.const import DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MP_DOMAIN


_LOGGER = logging.getLogger(__name__)


SERVICE_ADD_MEDIA = "add_to_playlist"
SERVICE_CALL_METHOD = "call_method"

ATTR_MEDIA_TYPE = "media_type"
ATTR_MEDIA_NAME = "media_name"
ATTR_MEDIA_ARTIST_NAME = "artist_name"
ATTR_MEDIA_ID = "media_id"
ATTR_METHOD = "method"

MEDIA_PLAYER_SCHEMA = vol.Schema({ATTR_ENTITY_ID: cv.comp_entity_ids})

KODI_ADD_MEDIA_SCHEMA = MEDIA_PLAYER_SCHEMA.extend(
    {
        vol.Required(ATTR_MEDIA_TYPE): cv.string,
        vol.Optional(ATTR_MEDIA_ID): cv.string,
        vol.Optional(ATTR_MEDIA_NAME): cv.string,
        vol.Optional(ATTR_MEDIA_ARTIST_NAME): cv.string,
    }
)
KODI_PLAYER_CALL_METHOD_SCHEMA = MEDIA_PLAYER_SCHEMA.extend(
    {vol.Required(ATTR_METHOD): cv.string}, extra=vol.ALLOW_EXTRA
)

SERVICE_TO_METHOD = {
    SERVICE_ADD_MEDIA: {
        "method": "async_add_media_to_playlist",
        "schema": KODI_ADD_MEDIA_SCHEMA,
    },
    SERVICE_CALL_METHOD: {
        "method": "async_call_method",
        "schema": KODI_CALL_METHOD_SCHEMA,
    },
}


async def async_setup(hass, config):
    """Setup the Kodi integration."""
    if any(
        ((CONF_PLATFORM, DOMAIN) in cfg.items() for cfg in config.get(MP_DOMAIN, []))
    ):
        # Register the Kodi media_player services
        _LOGGER.critical("Has Kodi media_player")

    # Return boolean to indicate that initialization was successful.
    return True
