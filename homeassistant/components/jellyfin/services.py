"""Services for the Jellyfin integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_MEDIA,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MP_DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

JELLYFIN_PLAY_MEDIA_SHUFFLE_SCHEMA = {
    vol.Required(ATTR_MEDIA_CONTENT_TYPE): cv.string,
    vol.Required(ATTR_MEDIA_CONTENT_ID): cv.string,
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


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Jellyfin component."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "play_media_shuffle",
        entity_domain=MP_DOMAIN,
        schema=vol.All(
            _promote_media_fields,
            cv.make_entity_service_schema(JELLYFIN_PLAY_MEDIA_SHUFFLE_SCHEMA),
        ),
        func="play_media_shuffle",
    )
