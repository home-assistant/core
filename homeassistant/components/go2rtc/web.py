"""Web views for go2rtc integration."""

from __future__ import annotations

import logging

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class Go2RtcHlsView(HomeAssistantView):
    """View to proxy HLS requests to go2rtc server."""

    url = r"/api/go2rtc/hls/{entity_id}/{file_name:.*}"
    name = "api:go2rtc:hls"
    requires_auth = False

    def __init__(self, hass: HomeAssistant, go2rtc_url: str) -> None:
        """Initialize the view."""
        self.hass = hass
        self.go2rtc_url = go2rtc_url.rstrip('/')

    async def get(self, request: web.Request, entity_id: str, file_name: str) -> web.Response:
        """Proxy HLS requests to go2rtc server."""
        # Validate entity_id exists and is accessible
        if entity_id not in self.hass.states.async_entity_ids("camera"):
            raise web.HTTPNotFound()

        # Proxy request to go2rtc server
        # go2rtc uses stream.m3u8?src=entity_id format
        if file_name == "playlist.m3u8":
            url = f"{self.go2rtc_url}/api/stream.m3u8"
            params = {"src": entity_id}
        else:
            # For segment files, proxy directly
            url = f"{self.go2rtc_url}/api/{file_name}"
            params = {"src": entity_id}
            
        params.update(request.query)
        
        session = async_get_clientsession(self.hass)
        
        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise web.HTTPNotFound()
                
                content_type = resp.headers.get('Content-Type', 'application/vnd.apple.mpegurl')
                body = await resp.read()
                
                return web.Response(
                    body=body,
                    content_type=content_type,
                    headers={'Access-Control-Allow-Origin': '*'}
                )
        except Exception as err:
            _LOGGER.error("Error proxying HLS request to go2rtc: %s", err)
            raise web.HTTPInternalServerError() from err