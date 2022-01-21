"""The media_source integration."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from urllib.parse import quote

import voluptuous as vol

from homeassistant.components import frontend, websocket_api
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    BrowseError,
    BrowseMedia,
)
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from . import local_source
from .const import DOMAIN, URI_SCHEME, URI_SCHEME_REGEX
from .error import MediaSourceError, Unresolvable
from .models import BrowseMediaSource, MediaSourceItem, PlayMedia

DEFAULT_EXPIRY_TIME = 3600 * 24

__all__ = [
    "DOMAIN",
    "is_media_source_id",
    "generate_media_source_id",
    "async_browse_media",
    "async_resolve_media",
    "BrowseMediaSource",
    "PlayMedia",
    "MediaSourceItem",
    "Unresolvable",
    "MediaSourceError",
]


def is_media_source_id(media_content_id: str) -> bool:
    """Test if identifier is a media source."""
    return URI_SCHEME_REGEX.match(media_content_id) is not None


def generate_media_source_id(domain: str, identifier: str) -> str:
    """Generate a media source ID."""
    uri = f"{URI_SCHEME}{domain or ''}"
    if identifier:
        uri += f"/{identifier}"
    return uri


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the media_source component."""
    hass.data[DOMAIN] = {}
    websocket_api.async_register_command(hass, websocket_browse_media)
    websocket_api.async_register_command(hass, websocket_resolve_media)
    frontend.async_register_built_in_panel(
        hass, "media-browser", "media_browser", "hass:play-box-multiple"
    )
    local_source.async_setup(hass)
    await async_process_integration_platforms(
        hass, DOMAIN, _process_media_source_platform
    )
    return True


async def _process_media_source_platform(
    hass: HomeAssistant, domain: str, platform: Any
) -> None:
    """Process a media source platform."""
    hass.data[DOMAIN][domain] = await platform.async_get_media_source(hass)


@callback
def _get_media_item(
    hass: HomeAssistant, media_content_id: str | None
) -> MediaSourceItem:
    """Return media item."""
    if media_content_id:
        return MediaSourceItem.from_uri(hass, media_content_id)

    # We default to our own domain if its only one registered
    domain = None if len(hass.data[DOMAIN]) > 1 else DOMAIN
    return MediaSourceItem(hass, domain, "")


@bind_hass
async def async_browse_media(
    hass: HomeAssistant,
    media_content_id: str,
    *,
    content_filter: Callable[[BrowseMedia], bool] | None = None,
) -> BrowseMediaSource:
    """Return media player browse media results."""
    if DOMAIN not in hass.data:
        raise BrowseError("Media Source not loaded")

    item = await _get_media_item(hass, media_content_id).async_browse()

    if content_filter is None or item.children is None:
        return item

    item.children = [
        child for child in item.children if child.can_expand or content_filter(child)
    ]
    return item


@bind_hass
async def async_resolve_media(hass: HomeAssistant, media_content_id: str) -> PlayMedia:
    """Get info to play media."""
    if DOMAIN not in hass.data:
        raise Unresolvable("Media Source not loaded")
    return await _get_media_item(hass, media_content_id).async_resolve()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "media_source/browse_media",
        vol.Optional(ATTR_MEDIA_CONTENT_ID, default=""): str,
    }
)
@websocket_api.async_response
async def websocket_browse_media(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Browse available media."""
    try:
        media = await async_browse_media(hass, msg.get("media_content_id", ""))
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
        vol.Optional("expires", default=DEFAULT_EXPIRY_TIME): int,
    }
)
@websocket_api.async_response
async def websocket_resolve_media(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
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
                quote(url),
                timedelta(seconds=msg["expires"]),
            )

        connection.send_result(msg["id"], {"url": url, "mime_type": media.mime_type})
