"""Services for the Jellyfin integration."""

import voluptuous as vol

from homeassistant.components.media_player import MEDIA_PLAYER_PLAY_MEDIA_SCHEMA
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_ENQUEUE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .media_player import JellyfinMediaPlayer

MEDIA_PLAYER_PLAY_MEDIA_JELLYFIN_SCHEMA = MEDIA_PLAYER_PLAY_MEDIA_SCHEMA.extend({
    vol.Exclusive(ATTR_MEDIA_SHUFFLE, "enqueue_announce"): cv.boolean,  
})


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Jellyfin component."""
    
    jellyfin_player = JellyfinMediaPlayer()

    # Re-register play_media to use the custom service schema
    hass.services.async_register(
        "media_player",
        "play_media",
        lambda service: jellyfin_player.play_media(
            service.data.get(ATTR_MEDIA_CONTENT_TYPE),
            service.data.get(ATTR_MEDIA_CONTENT_ID),
            shuffle=service.data.get(ATTR_MEDIA_SHUFFLE, False),
            enqueue=service.data.get(ATTR_MEDIA_ENQUEUE, None),
            extra=service.data.get(ATTR_MEDIA_EXTRA, {})
        ),
        schema=MEDIA_PLAYER_PLAY_MEDIA_JELLYFIN_SCHEMA,
    )
