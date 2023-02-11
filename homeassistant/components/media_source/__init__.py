"""The media_source integration."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.components import frontend, websocket_api
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    CONTENT_AUTH_EXPIRY_TIME,
    BrowseError,
    BrowseMedia,
)
from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.frame import report
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType
from homeassistant.loader import bind_hass

from . import local_source
from .const import (
    DOMAIN,
    MEDIA_CLASS_MAP,
    MEDIA_MIME_TYPES,
    URI_SCHEME,
    URI_SCHEME_REGEX,
)
from .error import MediaSourceError, Unresolvable
from .models import BrowseMediaSource, MediaSource, MediaSourceItem, PlayMedia

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
    "MediaSource",
    "MediaSourceError",
    "MEDIA_CLASS_MAP",
    "MEDIA_MIME_TYPES",
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
    hass: HomeAssistant, media_content_id: str | None, target_media_player: str | None
) -> MediaSourceItem:
    """Return media item."""
    if media_content_id:
        item = MediaSourceItem.from_uri(hass, media_content_id, target_media_player)
    else:
        # We default to our own domain if its only one registered
        domain = None if len(hass.data[DOMAIN]) > 1 else DOMAIN
        return MediaSourceItem(hass, domain, "", target_media_player)

    if item.domain is not None and item.domain not in hass.data[DOMAIN]:
        raise ValueError("Unknown media source")

    return item


@bind_hass
async def async_browse_media(
    hass: HomeAssistant,
    media_content_id: str | None,
    *,
    content_filter: Callable[[BrowseMedia], bool] | None = None,
) -> BrowseMediaSource:
    """Return media player browse media results."""
    if DOMAIN not in hass.data:
        raise BrowseError("Media Source not loaded")

    try:
        item = await _get_media_item(hass, media_content_id, None).async_browse()
    except ValueError as err:
        raise BrowseError(str(err)) from err

    if content_filter is None or item.children is None:
        return item

    old_count = len(item.children)
    item.children = [
        child for child in item.children if child.can_expand or content_filter(child)
    ]
    item.not_shown += old_count - len(item.children)
    return item


@bind_hass
async def async_resolve_media(
    hass: HomeAssistant,
    media_content_id: str,
    target_media_player: str | None | UndefinedType = UNDEFINED,
) -> PlayMedia:
    """Get info to play media."""
    if DOMAIN not in hass.data:
        raise Unresolvable("Media Source not loaded")

    if target_media_player is UNDEFINED:
        report("calls media_source.async_resolve_media without passing an entity_id")
        target_media_player = None

    try:
        item = _get_media_item(hass, media_content_id, target_media_player)
    except ValueError as err:
        raise Unresolvable(str(err)) from err

    return await item.async_resolve()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "media_source/browse_media",
        vol.Optional(ATTR_MEDIA_CONTENT_ID, default=""): str,
    }
)
@websocket_api.async_response
async def websocket_browse_media(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
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
        vol.Optional("expires", default=CONTENT_AUTH_EXPIRY_TIME): int,
    }
)
@websocket_api.async_response
async def websocket_resolve_media(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Resolve media."""
    try:
        media = await async_resolve_media(hass, msg["media_content_id"])
    except Unresolvable as err:
        connection.send_error(msg["id"], "resolve_media_failed", str(err))
        return

    connection.send_result(
        msg["id"],
        {
            "url": async_process_play_media_url(
                hass, media.url, allow_relative_url=True
            ),
            "mime_type": media.mime_type,
        },
    )
