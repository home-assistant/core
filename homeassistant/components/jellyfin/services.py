"""Services for the Jellyfin integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerEnqueue,
    _promote_media_fields,
    _rename_keys,
)
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_SHUFFLE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

# custom media player input schema adding 'shuffle'
JELYFIN_PLAY_MEDIA_SCHEMA = vol.All(
    _promote_media_fields,
    cv.make_entity_service_schema({
        vol.Required(ATTR_MEDIA_CONTENT_TYPE): cv.string,
        vol.Required(ATTR_MEDIA_CONTENT_ID): cv.string,
        vol.Exclusive(ATTR_MEDIA_ENQUEUE, "enqueue_announce"): vol.Any(
            cv.boolean, vol.Coerce(MediaPlayerEnqueue)
        ),
        vol.Exclusive(ATTR_MEDIA_ANNOUNCE, "enqueue_announce"): cv.boolean,
        vol.Exclusive(ATTR_MEDIA_SHUFFLE, "enqueue_announce"): cv.boolean,
        vol.Optional(ATTR_MEDIA_EXTRA, default={}): dict,
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
    # only setup once
    if hass.services.has_service(DOMAIN, "play_media"):
        return

    # the player service which gets component and entity
    async def play_media_service_handler(call: ServiceCall):
        component = hass.data.get("entity_components", {}).get("media_player")
        if component is None:
            return

        # solve a circular ImportError
        from .media_player import JellyfinMediaPlayer

        entity_ids: list[str] = call.data.get("entity_id", [])
        kwargs: dict[str, Any] = {
            ATTR_MEDIA_SHUFFLE: call.data.get(ATTR_MEDIA_SHUFFLE, False),
            ATTR_MEDIA_ENQUEUE: call.data.get(ATTR_MEDIA_ENQUEUE, None),
            ATTR_MEDIA_EXTRA: call.data.get(ATTR_MEDIA_EXTRA, {}),
        }

        for entity_id in entity_ids:
            entity = component.get_entity(entity_id)
            if not isinstance(entity, JellyfinMediaPlayer):
                continue
            entity.play_media(
                media_type=call.data[ATTR_MEDIA_CONTENT_TYPE],
                media_id=call.data[ATTR_MEDIA_CONTENT_ID],
                **kwargs,
            )

    # register play_media to use the custom service schema
    hass.services.async_register(
        DOMAIN,
        "play_media",
        play_media_service_handler,
        schema=JELLYFIN_PLAY_MEDIA_SCHEMA,
    )
