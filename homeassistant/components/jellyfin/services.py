"""Services for the Jellyfin integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_MEDIA,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_EXTRA,
    DOMAIN as MP_DOMAIN,
    MediaPlayerEntity,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

JELLYFIN_PLAY_MEDIA_SHUFFLE_SCHEMA = {
    vol.Required(ATTR_MEDIA_CONTENT_TYPE): cv.string,
    vol.Required(ATTR_MEDIA_CONTENT_ID): cv.string,
    vol.Optional(ATTR_MEDIA_EXTRA, default={}): dict,
}


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

    async def play_media_shuffle_service_handler(
        entity: MediaPlayerEntity, call: ServiceCall
    ) -> None:

        await hass.async_add_executor_job(
            lambda: entity.play_media_shuffle(
                media_type=call.data["media_type"],
                media_id=call.data["media_id"],
            )
        )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "play_media_shuffle",
        entity_domain=MP_DOMAIN,
        schema=vol.All(
            _promote_media_fields,
            cv.make_entity_service_schema(JELLYFIN_PLAY_MEDIA_SHUFFLE_SCHEMA),
            _rename_keys(
                media_type=ATTR_MEDIA_CONTENT_TYPE,
                media_id=ATTR_MEDIA_CONTENT_ID,
            ),
        ),
        func=play_media_shuffle_service_handler,
    )
