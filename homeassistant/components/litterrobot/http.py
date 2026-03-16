"""HTTP view for serving Litter-Robot local recordings with range request support."""

from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web
from aiohttp.web_exceptions import HTTPForbidden, HTTPNotFound

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

RECORDING_ENDPOINT = "/api/litterrobot/recordings/{serial}/{filename}"
RECORDING_VIEW_NAME = "api:litterrobot:recordings"
PLAYER_ENDPOINT = "/api/litterrobot/player/{serial}/{filename}"
PLAYER_VIEW_NAME = "api:litterrobot:player"

# Set at integration setup time
_media_root: Path | None = None


def async_setup_recording_view(hass: HomeAssistant, media_root: Path) -> None:
    """Register the recording HTTP view."""
    global _media_root  # noqa: PLW0603
    _media_root = media_root
    if hass.http is not None:
        hass.http.register_view(LitterRobotRecordingView)
        hass.http.register_view(LitterRobotPlayerView)


class LitterRobotRecordingView(HomeAssistantView):
    """Serve local Litter-Robot MP4 recordings.

    Uses aiohttp FileResponse which handles HTTP Range requests natively,
    enabling seeking and progressive playback on mobile clients.
    """

    url = RECORDING_ENDPOINT
    name = RECORDING_VIEW_NAME
    requires_auth = True

    async def get(
        self,
        request: web.Request,
        serial: str,
        filename: str,
    ) -> web.FileResponse:
        """Serve an MP4 recording file."""
        if _media_root is None:
            raise HTTPNotFound

        # Prevent path traversal — resolve and verify under media root
        file_path = (_media_root / serial / filename).resolve()
        if not file_path.is_relative_to(_media_root.resolve()):
            raise HTTPForbidden

        if not file_path.exists() or not file_path.is_file():
            raise HTTPNotFound

        return web.FileResponse(file_path)


class LitterRobotPlayerView(HomeAssistantView):
    """Serve an HTML video player page for a recording."""

    url = PLAYER_ENDPOINT
    name = PLAYER_VIEW_NAME
    requires_auth = True

    async def get(
        self,
        request: web.Request,
        serial: str,
        filename: str,
    ) -> web.Response:
        """Serve an HTML page with a video player."""
        if _media_root is None:
            raise HTTPNotFound

        if "/" in filename or "\\" in filename or ".." in filename:
            raise HTTPForbidden

        file_path = (_media_root / serial / filename).resolve()
        if not file_path.is_relative_to(_media_root.resolve()):
            raise HTTPForbidden

        if not file_path.exists() or not file_path.is_file():
            raise HTTPNotFound

        video_url = f"/api/litterrobot/recordings/{serial}/{filename}"
        html = (
            "<!DOCTYPE html>"
            "<html><head>"
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<style>"
            "body{margin:0;background:#1c1c1c;display:flex;"
            "align-items:center;justify-content:center;height:100vh}"
            "video{max-width:100%;max-height:100%}"
            "</style>"
            "</head><body>"
            f'<video controls autoplay playsinline width="100%">'
            f'<source src="{video_url}" type="video/mp4">'
            "</video>"
            "</body></html>"
        )
        return web.Response(text=html, content_type="text/html")
