"""Support for interfacing with the XBMC/Kodi JSON-RPC API."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN

SERVICE_ADD_MEDIA = "add_to_playlist"
SERVICE_CALL_METHOD = "call_method"

ATTR_MEDIA_TYPE = "media_type"
ATTR_MEDIA_NAME = "media_name"
ATTR_MEDIA_ARTIST_NAME = "artist_name"
ATTR_MEDIA_ID = "media_id"
ATTR_METHOD = "method"


KODI_ADD_MEDIA_SCHEMA: VolDictType = {
    vol.Required(ATTR_MEDIA_TYPE): cv.string,
    vol.Optional(ATTR_MEDIA_ID): cv.string,
    vol.Optional(ATTR_MEDIA_NAME): cv.string,
    vol.Optional(ATTR_MEDIA_ARTIST_NAME): cv.string,
}

KODI_CALL_METHOD_SCHEMA = cv.make_entity_service_schema(
    {vol.Required(ATTR_METHOD): cv.string}, extra=vol.ALLOW_EXTRA
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ADD_MEDIA,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=KODI_ADD_MEDIA_SCHEMA,
        func="async_add_media_to_playlist",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CALL_METHOD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=KODI_CALL_METHOD_SCHEMA,
        func="async_call_method",
    )
