"""Assist satellite HTTP views."""

import logging
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView

_LOGGER = logging.getLogger(__name__)

PREANNOUNCE_CONTENT_TYPE = "audio/mpeg"
PREANNOUNCE_FILENAME = "preannounce.mp3"
PREANNOUNCE_URL = f"/api/assist_satellite/{PREANNOUNCE_FILENAME}"


class PreannounceSoundView(HomeAssistantView):
    """View to serve the default pre-announcement sound."""

    requires_auth = False
    url = PREANNOUNCE_URL
    name = "api:assist_satellite_preannounce_mp3"

    async def get(self, request: web.Request) -> web.Response:
        """Start a get request."""
        hass = request.app[KEY_HASS]
        audio_path = Path(__file__).parent / PREANNOUNCE_FILENAME
        audio_data = await hass.async_add_executor_job(audio_path.read_bytes)

        return web.Response(body=audio_data, content_type=PREANNOUNCE_CONTENT_TYPE)
