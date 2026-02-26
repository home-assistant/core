"""Services for the Jellyfin integration."""

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_PLAYER_PLAY_MEDIA_SCHEMA,
    _promote_media_fields,
    _rename_keys,
)
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

def create_jellyfin_media_player_schema():
    return vol.All(
        _promote_media_fields,
        cv.make_entity_service_schema({
            **MEDIA_PLAYER_PLAY_MEDIA_SCHEMA,
            vol.Exclusive(ATTR_MEDIA_SHUFFLE, "enqueue_announce"): cv.boolean,
        }),
        _rename_keys(
            media_type=ATTR_MEDIA_CONTENT_TYPE,
            media_id=ATTR_MEDIA_CONTENT_ID,
            enqueue=ATTR_MEDIA_ENQUEUE,
            shuffle=ATTR_MEDIA_SHUFFLE,
        ),
    )

async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Jellyfin component."""
    
    MEDIA_PLAYER_PLAY_MEDIA_JELLYFIN_SCHEMA = create_jellyfin_media_player_schema()

    async def play_media_service_handler(service):
        await JellyfinMediaPlayer.play_media(
            media_type=service.data.get(ATTR_MEDIA_CONTENT_TYPE),
            media_id=service.data.get(ATTR_MEDIA_CONTENT_ID),
            shuffle=service.data.get(ATTR_MEDIA_SHUFFLE, False),
            enqueue=service.data.get(ATTR_MEDIA_ENQUEUE, None),
            extra=service.data.get(ATTR_MEDIA_EXTRA, {})
        )

    # Re-register play_media to use the custom service schema
    hass.services.async_register(
        "media_player",
        "play_media",
        play_media_service_handler,
        schema=MEDIA_PLAYER_PLAY_MEDIA_JELLYFIN_SCHEMA,
    )
