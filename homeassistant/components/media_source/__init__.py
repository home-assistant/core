"""The media_source integration."""
from typing import Optional

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.media_player.const import ATTR_MEDIA_CONTENT_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.loader import bind_hass

from . import local_source, models
from .const import DOMAIN, URI_SCHEME, URI_SCHEME_REGEX

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


def is_media_source_id(media_content_id: str):
    """Test if identifier is a media source."""
    return URI_SCHEME_REGEX.match(media_content_id) is not None


def generate_media_source_id(domain: str, identifier: str) -> str:
    """Generate a media source ID."""
    return f"{URI_SCHEME}{domain}/{identifier}"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the media_source component."""
    hass.data[DOMAIN] = {}
    hass.components.websocket_api.async_register_command(websocket_browse_media)
    local_source.async_setup(hass)
    await async_process_integration_platforms(
        hass, DOMAIN, _process_media_source_platform
    )
    return True


async def _process_media_source_platform(hass, domain, platform):
    """Process a media source platform."""
    hass.data[DOMAIN][domain] = await platform.async_get_media_source(hass)


@callback
def _get_media_item(
    hass: HomeAssistant, media_content_id: Optional[str]
) -> models.MediaSourceItem:
    """Return media item."""
    if media_content_id:
        return models.MediaSourceItem.from_uri(hass, media_content_id)

    # We default to our own domain if its only one registered
    domain = None if len(hass.data[DOMAIN]) > 1 else DOMAIN
    return models.MediaSourceItem(hass, domain, "")


@bind_hass
async def async_browse_media(
    hass: HomeAssistant, media_content_id: str
) -> models.BrowseMedia:
    """Return media player browse media results."""
    return await _get_media_item(hass, media_content_id).async_browse()


@bind_hass
async def async_resolve_media(
    hass: HomeAssistant, media_content_id: str
) -> models.PlayMedia:
    """Get info to play media."""
    return await _get_media_item(hass, media_content_id).async_resolve()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "media_source/browse_media",
        vol.Optional(ATTR_MEDIA_CONTENT_ID, default=""): str,
    }
)
@websocket_api.async_response
async def websocket_browse_media(hass, connection, msg):
    """Browse available media."""
    media = await async_browse_media(hass, msg.get("media_content_id"))
    connection.send_result(
        msg["id"],
        media.to_media_player_item(),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "media_source/resolve_media",
        vol.Required(ATTR_MEDIA_CONTENT_ID): str,
    }
)
@websocket_api.async_response
async def websocket_resolve_media(hass, connection, msg):
    """Resolve media."""
    media = await async_resolve_media(hass, msg.get("media_content_id"))
    connection.send_result(msg["id"], {"url": media.url, "mime_type": media.mime_type})
