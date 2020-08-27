"""The media_finder integration."""
import mimetypes
from pathlib import Path

from aiohttp import web
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.static import CACHE_HEADERS
from homeassistant.components.media_player.const import ATTR_MEDIA_CONTENT_ID
from homeassistant.core import HomeAssistant
from homeassistant.loader import bind_hass

from .const import DOMAIN, MEDIA_MIME_TYPES

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the media_finder component."""
    hass.http.register_view(MediaView(hass))
    hass.components.websocket_api.async_register_command(websocket_browse_media)
    return True


@bind_hass
async def async_find_media(hass: HomeAssistant, path=None, mime_types=MEDIA_MIME_TYPES):
    """
    Return a payload for the "media_finder/browse_media" websocket command.

    Payload should follow this format:
        {
            "title": str - Title of the item
            "media_content_type": str - see below
            "media_content_id": str - see below
                - Can be passed back in to browse further
                - Can be used as-is with media_player.play_media service
            "can_play": bool - If item is playable
            "can_expand": bool - If item contains other media
            "thumbnail": str (Optional) - URL to image thumbnail for item
            "children": list (Optional) - [{<item_with_keys_above>}, ...]
        }
    """

    prefix = "/media"

    def build_item_response(path, is_child=False):
        # Grab path without /media
        path = Path(path[path.startswith(prefix) and len(prefix) :])
        mime_type, _ = mimetypes.guess_type(str(path))

        response = {
            "title": path.name,
            "media_content_type": mime_type or "",
            "media_content_id": f"{prefix}{str(path)}",
            "can_play": path.is_file(),
            "can_expand": path.is_dir(),
        }

        # Make sure it's a file or directory
        if not response["can_play"] and not response["can_expand"]:
            return None

        # Check that it's a media file
        if response["can_play"] and (
            not mime_type or mime_type.split("/")[0] not in mime_types
        ):
            return None

        if response["can_expand"]:
            response["title"] += "/"
            # Append first level children
            if not is_child:
                response["children"] = []
                for child_path in path.iterdir():
                    child = build_item_response(str(child_path), True)
                    if child:
                        response["children"].append(child)

        return response

    if not path or path == prefix:
        return {
            "title": "Local Media",
            "media_content_type": "",
            "media_content_id": prefix,
            "can_play": False,
            "can_expand": True,
            "children": [
                await hass.async_add_executor_job(
                    build_item_response, external_dir, True
                )
                for external_dir in hass.config.allowlist_external_dirs
            ],
        }

    return await hass.async_add_executor_job(build_item_response, path)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "media_finder/browse_media",
        vol.Optional(
            ATTR_MEDIA_CONTENT_ID,
            "media_ids",
            "media_content_type and media_content_id must be provided together",
        ): str,
    }
)
@websocket_api.async_response
async def websocket_browse_media(hass, connection, msg):
    """
    Browse available media.

    To use, media_player integrations can implement MediaPlayerEntity.async_browse_media()
    """
    media_content_id = msg.get(ATTR_MEDIA_CONTENT_ID)

    return await async_find_media(hass, media_content_id)


class MediaView(HomeAssistantView):
    """
    Media Finder View.

    Returns media files exposed through allowlist.
    """

    url = "/media/{path:.*}"
    name = "media"

    def __init__(self, hass: HomeAssistant):
        """Initialize the media view."""
        self.hass = hass
        super().__init__()

    async def get(self, request: web.Request, path: str) -> web.FileResponse:
        """Start a GET request."""

        media_path = Path(f"/{path}")

        # Check that the file exists
        if not media_path.is_file():
            raise web.HTTPNotFound()

        # Check for file access
        if not self.hass.config.is_allowed_path(str(media_path)):
            raise web.HTTPUnauthorized()

        # Check that it's a media file
        mime_type, _ = mimetypes.guess_type(str(media_path))
        if not mime_type or mime_type.split("/")[0] not in MEDIA_MIME_TYPES:
            raise web.HTTPNotFound()

        return web.FileResponse(media_path, headers=CACHE_HEADERS)
