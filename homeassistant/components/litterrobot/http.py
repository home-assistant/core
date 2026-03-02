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

# Set at integration setup time
_media_root: Path | None = None


def async_setup_recording_view(hass: HomeAssistant, media_root: Path) -> None:
    """Register the recording HTTP view."""
    global _media_root  # noqa: PLW0603
    _media_root = media_root
    hass.http.register_view(LitterRobotRecordingView)


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
