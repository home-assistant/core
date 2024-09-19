"""Assist satellite connection test."""

import logging
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)

CONNECTION_TEST_CONTENT_TYPE = "audio/mpeg"
CONNECTION_TEST_FILENAME = "connection_test.mp3"
CONNECTION_TEST_SIGNAL = "assist_satellite.connection_test_{}"
CONNECTION_TEST_URL_BASE = "/api/assist_satellite/connection_test"


class ConnectionTestView(HomeAssistantView):
    """View to serve an audio sample for connection test."""

    requires_auth = False
    url = CONNECTION_TEST_URL_BASE + "/{connection_id}"
    name = "api:assist_satellite_connection_test"

    async def get(self, request: web.Request, connection_id: str) -> web.Response:
        """Start a get request."""
        _LOGGER.debug("Request for connection test with id %s", connection_id)
        _LOGGER.warning("Request for connection test with id %s", connection_id)

        hass = request.app[KEY_HASS]
        audio_path = Path(__file__).parent / CONNECTION_TEST_FILENAME
        audio_data = await hass.async_add_executor_job(audio_path.read_bytes)

        async_dispatcher_send(hass, CONNECTION_TEST_SIGNAL.format(connection_id))
        return web.Response(body=audio_data, content_type=CONNECTION_TEST_CONTENT_TYPE)
