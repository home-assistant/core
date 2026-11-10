"""Support for interfacing with the XBMC/Kodi JSON-RPC API."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class KodiService(StrEnum):
    """Store keys for Kodi services."""

    ADD_TO_PLAYLIST = "add_to_playlist"
    CALL_METHOD = "call_method"


class KodiServiceArgument(StrEnum):
    """Store keys for Kodi service arguments."""

    MEDIA_TYPE = "media_type"
    MEDIA_ID = "media_id"
    MEDIA_NAME = "media_name"
    ARTIST_NAME = "artist_name"
    METHOD = "method"


KODI_ADD_MEDIA_SCHEMA: VolDictType = {
    probatio.Required(KodiServiceArgument.MEDIA_TYPE): cv.string,
    probatio.Optional(KodiServiceArgument.MEDIA_ID): cv.string,
    probatio.Optional(KodiServiceArgument.MEDIA_NAME): cv.string,
    probatio.Optional(KodiServiceArgument.ARTIST_NAME): cv.string,
}

KODI_CALL_METHOD_SCHEMA = cv.make_entity_service_schema(
    {probatio.Required(KodiServiceArgument.METHOD): cv.string},
    extra=probatio.ALLOW_EXTRA,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        KodiService.ADD_TO_PLAYLIST,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=KODI_ADD_MEDIA_SCHEMA,
        func="async_add_media_to_playlist",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        KodiService.CALL_METHOD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=KODI_CALL_METHOD_SCHEMA,
        func="async_call_method",
    )
