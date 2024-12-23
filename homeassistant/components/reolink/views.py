"""Reolink Integration views."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.ssl import SSLCipherList

_LOGGER = logging.getLogger(__name__)


@callback
def async_generate_playback_proxy_url(config_entry_id: str, channel: str, filename: str, stream_res: str, vod_type: str) -> str:
    """Generate proxy URL for event video."""

    url_format = PlaybackProxyView.url
    return url_format.format(config_entry_id=config_entry_id, channel=channel, filename=filename, stream_res=stream_res, vod_type=vod_type)


class PlaybackProxyView(HomeAssistantView):
    """View to proxy playback video from Reolink."""

    requires_auth = True
    url = "/api/reolink/video/{config_entry_id}/{channel}/{filename}/{stream_res}/{vod_type}"
    name = "api:reolink_playback"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a proxy view."""
        self.hass = hass
        self.session = async_get_clientsession(
            hass,
            verify_ssl=False,
            ssl_cipher=SSLCipherList.INSECURE,
        )

    async def get(
        self, request: web.Request, config_entry_id: str, channel: str, filename: str, stream_res: str, vod_type: str
    ) -> web.StreamResponse:
        """Get Camera Video clip for an event."""
        _LOGGER.error("YES")
        host = get_host(self.hass, config_entry_id)
        
        try:
            mime_type, reolink_url = await host.api.get_vod_source(
                channel, filename, stream_res, vod_type
            )
        except ReolinkError as err:
            _LOGGER.warning("Reolink playback proxy error: %s", str(err))
            web.Response(body=str(err), status=HTTPStatus.BAD_REQUEST)

        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "video/mp4",
            },
        )
        
        reolink_response = await self.session.request(
            "GET",
            reolink_url,
            timeout=0,
        )
        
        _LOGGER.error(reolink_response.status)
        _LOGGER.error(reolink_response.reason)
        _LOGGER.error(reolink_response.headers)
        
        return reolink_response        
