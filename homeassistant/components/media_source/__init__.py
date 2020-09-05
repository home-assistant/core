"""The media_source integration."""
from datetime import timedelta
from typing import Optional

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player.const import ATTR_MEDIA_CONTENT_ID
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.loader import bind_hass

from . import local_source, models
from .const import DOMAIN, URI_SCHEME, URI_SCHEME_REGEX
from .error import Unresolvable


def is_media_source_id(media_content_id: str):
    """Test if identifier is a media source."""
    return URI_SCHEME_REGEX.match(media_content_id) is not None


def generate_media_source_id(domain: str, identifier: str) -> str:
    """Generate a media source ID."""
    uri = f"{URI_SCHEME}{domain or ''}"
    if identifier:
        uri += f"/{identifier}"
    return uri


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the media_source component."""
    hass.data[DOMAIN] = {}
    hass.components.websocket_api.async_register_command(websocket_browse_media)
    hass.components.websocket_api.async_register_command(websocket_resolve_media)
    hass.components.frontend.async_register_built_in_panel(
        "media-browser", "media-browser", "hass:play-box-multiple"
    )
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
) -> models.BrowseMediaSource:
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
    try:
        media = await async_browse_media(hass, msg.get("media_content_id"))
        connection.send_result(
            msg["id"],
            media.as_dict(),
        )
    except BrowseError as err:
        connection.send_error(msg["id"], "browse_media_failed", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "media_source/resolve_media",
        vol.Required(ATTR_MEDIA_CONTENT_ID): str,
        vol.Optional("expires", default=30): int,
    }
)
@websocket_api.async_response
async def websocket_resolve_media(hass, connection, msg):
    """Resolve media."""
    try:
        media = await async_resolve_media(hass, msg["media_content_id"])
        url = media.url
    except Unresolvable as err:
        connection.send_error(msg["id"], "resolve_media_failed", str(err))
    else:
        if url[0] == "/":
            url = async_sign_path(
                hass,
                connection.refresh_token_id,
                url,
                timedelta(seconds=msg["expires"]),
            )

        connection.send_result(msg["id"], {"url": url, "mime_type": media.mime_type})
