"""Services for the Jellyfin integration."""

from enum import StrEnum
from typing import Any

import probatio

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as MP_DOMAIN,
    MediaPlayerEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class JellyfinService(StrEnum):
    """Store keys for Jellyfin services."""

    PLAY_MEDIA_SHUFFLE = "play_media_shuffle"


class JellyfinServiceArgument(StrEnum):
    """Store keys for Jellyfin service arguments."""

    MEDIA = "media"
    MEDIA_CONTENT_ID = "media_content_id"


JELLYFIN_PLAY_MEDIA_SHUFFLE_SCHEMA = {
    probatio.Required(JellyfinServiceArgument.MEDIA_CONTENT_ID): cv.string,
}


def _promote_media_fields(data: dict[str, Any]) -> dict[str, Any]:
    """If 'media' key exists, promote its fields to the top level."""
    if JellyfinServiceArgument.MEDIA in data and isinstance(
        data[JellyfinServiceArgument.MEDIA], dict
    ):
        if JellyfinServiceArgument.MEDIA_CONTENT_ID in data:
            raise probatio.Invalid(
                "Play media cannot contain both"
                f" '{JellyfinServiceArgument.MEDIA}' and"
                f" '{JellyfinServiceArgument.MEDIA_CONTENT_ID}'"
            )
        media_data = data[JellyfinServiceArgument.MEDIA]

        if ATTR_MEDIA_CONTENT_ID in media_data:
            data[JellyfinServiceArgument.MEDIA_CONTENT_ID] = media_data[
                ATTR_MEDIA_CONTENT_ID
            ]

        del data[JellyfinServiceArgument.MEDIA]
    return data


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Jellyfin component."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        JellyfinService.PLAY_MEDIA_SHUFFLE,
        entity_domain=MP_DOMAIN,
        schema=probatio.All(
            _promote_media_fields,
            cv.make_entity_service_schema(JELLYFIN_PLAY_MEDIA_SHUFFLE_SCHEMA),
        ),
        func="play_media_shuffle",
        required_features=MediaPlayerEntityFeature.PLAY_MEDIA,
    )
