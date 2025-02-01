"""Assist satellite connection test."""

import logging
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView

from .const import CONNECTION_TEST_DATA

_LOGGER = logging.getLogger(__name__)

CONNECTION_TEST_CONTENT_TYPE = "audio/mpeg"
CONNECTION_TEST_FILENAME = "connection_test.mp3"
CONNECTION_TEST_URL_BASE = "/api/assist_satellite/connection_test"


class ConnectionTestView(HomeAssistantView):
    """View to serve an audio sample for connection test."""

    requires_auth = False
    url = f"{CONNECTION_TEST_URL_BASE}/{{connection_id}}"
    name = "api:assist_satellite_connection_test"

    async def get(self, request: web.Request, connection_id: str) -> web.Response:
        """Start a get request."""
        _LOGGER.debug("Request for connection test with id %s", connection_id)

        hass = request.app[KEY_HASS]
        connection_test_data = hass.data[CONNECTION_TEST_DATA]

        connection_test_event = connection_test_data.pop(connection_id, None)

        if connection_test_event is None:
            return web.Response(status=404)

        connection_test_event.set()

        audio_path = Path(__file__).parent / CONNECTION_TEST_FILENAME
        audio_data = await hass.async_add_executor_job(audio_path.read_bytes)

        return web.Response(body=audio_data, content_type=CONNECTION_TEST_CONTENT_TYPE)
