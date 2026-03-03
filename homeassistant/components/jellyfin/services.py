"""Services for the Jellyfin integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_MEDIA,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_SHUFFLE,
    DOMAIN as MP_DOMAIN,
    MEDIA_PLAYER_PLAY_MEDIA_SCHEMA as MP_PLAY_MEDIA_SCHEMA,
    MediaPlayerEntity,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .media_player import JellyfinMediaPlayer

# customize media player input schema adding 'shuffle'
JELLYFIN_PLAY_MEDIA_SCHEMA = (MP_PLAY_MEDIA_SCHEMA - {ATTR_MEDIA_ENQUEUE}) | {vol.Exclusive(ATTR_MEDIA_SHUFFLE, "shuffle"): cv.boolean}

def _promote_media_fields(data: dict[str, Any]) -> dict[str, Any]:
    """If 'media' key exists, promote its fields to the top level."""
    if ATTR_MEDIA in data and isinstance(data[ATTR_MEDIA], dict):
        if ATTR_MEDIA_CONTENT_TYPE in data or ATTR_MEDIA_CONTENT_ID in data:
            raise vol.Invalid(
                f"Play media cannot contain '{ATTR_MEDIA}' and '{ATTR_MEDIA_CONTENT_ID}' or '{ATTR_MEDIA_CONTENT_TYPE}'"
            )
        media_data = data[ATTR_MEDIA]

        if ATTR_MEDIA_CONTENT_TYPE in media_data:
            data[ATTR_MEDIA_CONTENT_TYPE] = media_data[ATTR_MEDIA_CONTENT_TYPE]
        if ATTR_MEDIA_CONTENT_ID in media_data:
            data[ATTR_MEDIA_CONTENT_ID] = media_data[ATTR_MEDIA_CONTENT_ID]

        del data[ATTR_MEDIA]
    return data

def _rename_keys(**keys: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Create validator that renames keys.

    Necessary because the service schema names do not match the command parameters.

    Async friendly.
    """
    def rename(value: dict[str, Any]) -> dict[str, Any]:
        for to_key, from_key in keys.items():
            if from_key in value:
                value[to_key] = value.pop(from_key)
        return value
    return rename


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Jellyfin component."""
    # only setup once
    if hass.services.has_service(DOMAIN, "play_media"):
        return

    # the player service
    async def play_media_service_handler(entity: MediaPlayerEntity,
                                         call: ServiceCall) -> None:
        kwargs: dict[str, Any] = {
            ATTR_MEDIA_SHUFFLE: call.data.get(ATTR_MEDIA_SHUFFLE, False),
            ATTR_MEDIA_ENQUEUE: call.data.get(ATTR_MEDIA_ENQUEUE, None),
            ATTR_MEDIA_EXTRA: call.data.get(ATTR_MEDIA_EXTRA, {}),
        }

        if not isinstance(entity, JellyfinMediaPlayer):
            return

        def _play(e=entity) -> None:
            e.play_media(
                media_type=call.data["media_type"],
                media_id=call.data["media_id"],
                **kwargs,
            )

        await hass.async_add_executor_job(_play)

    # register play_media to use the custom service schema
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "play_media",
        entity_domain=MP_DOMAIN,
        schema=vol.All(
            _promote_media_fields,
            cv.make_entity_service_schema(JELLYFIN_PLAY_MEDIA_SCHEMA),
            _rename_keys(
                media_type=ATTR_MEDIA_CONTENT_TYPE,
                media_id=ATTR_MEDIA_CONTENT_ID,
                enqueue=ATTR_MEDIA_ENQUEUE,
                shuffle=ATTR_MEDIA_SHUFFLE,
            ),
        ),
        func=play_media_service_handler,
    )
