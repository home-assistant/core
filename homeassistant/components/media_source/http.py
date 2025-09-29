"""HTTP views and WebSocket commands for media sources."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import frontend, websocket_api
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    CONTENT_AUTH_EXPIRY_TIME,
    BrowseError,
    async_process_play_media_url,
)
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant

from .error import Unresolvable
from .helper import async_browse_media, async_resolve_media


def async_setup(hass: HomeAssistant) -> None:
    """Set up the HTTP views and WebSocket commands for media sources."""
    websocket_api.async_register_command(hass, websocket_browse_media)
    websocket_api.async_register_command(hass, websocket_resolve_media)
    frontend.async_register_built_in_panel(
        hass, "media-browser", "media_browser", "hass:play-box-multiple"
    )


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
        media = await async_resolve_media(hass, msg["media_content_id"], None)
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
