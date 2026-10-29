"""Support for interfacing with the XBMC/Kodi JSON-RPC API."""

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DEFAULT_NOTIFY_DISPLAYTIME, DEFAULT_NOTIFY_ICON, DOMAIN

SERVICE_ADD_MEDIA = "add_to_playlist"
SERVICE_CALL_METHOD = "call_method"
SERVICE_SEND_MESSAGE = "send_message"

ATTR_MEDIA_TYPE = "media_type"
ATTR_MEDIA_NAME = "media_name"
ATTR_MEDIA_ARTIST_NAME = "artist_name"
ATTR_MEDIA_ID = "media_id"
ATTR_METHOD = "method"
ATTR_MESSAGE = "message"
ATTR_TITLE = "title"
ATTR_DISPLAYTIME = "displaytime"


KODI_ADD_MEDIA_SCHEMA: VolDictType = {
    probatio.Required(ATTR_MEDIA_TYPE): cv.string,
    probatio.Optional(ATTR_MEDIA_ID): cv.string,
    probatio.Optional(ATTR_MEDIA_NAME): cv.string,
    probatio.Optional(ATTR_MEDIA_ARTIST_NAME): cv.string,
}

KODI_CALL_METHOD_SCHEMA = cv.make_entity_service_schema(
    {probatio.Required(ATTR_METHOD): cv.string}, extra=probatio.ALLOW_EXTRA
)

KODI_SEND_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {
        probatio.Required(ATTR_MESSAGE): cv.string,
        probatio.Optional(ATTR_TITLE): cv.string,
        probatio.Optional(ATTR_ICON, default=DEFAULT_NOTIFY_ICON): cv.string,
        # Kodi shows a notification for at least 1.5 seconds
        probatio.Optional(
            ATTR_DISPLAYTIME, default=DEFAULT_NOTIFY_DISPLAYTIME
        ): probatio.All(probatio.Coerce(int), probatio.Range(min=1500)),
    }
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
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema=KODI_SEND_MESSAGE_SCHEMA,
        func="kodi_send_message",
    )
