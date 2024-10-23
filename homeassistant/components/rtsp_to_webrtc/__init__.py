"""RTSPtoWebRTC integration with an external RTSPToWebRTC Server.

WebRTC uses a direct communication from the client (e.g. a web browser) to a
camera device. Home Assistant acts as the signal path for initial set up,
passing through the client offer and returning a camera answer, then the client
and camera communicate directly.

However, not all cameras natively support WebRTC. This integration is a shim
for camera devices that support RTSP streams only, relying on an external
server RTSPToWebRTC that is a proxy. Home Assistant does not participate in
the offer/answer SDP protocol, other than as a signal path pass through.

Other integrations may use this integration with these steps:
- Check if this integration is loaded
- Call is_supported_stream_source for compatibility
- Call async_offer_for_stream_source to get back an answer for a client offer
"""

from __future__ import annotations

import asyncio
import logging

from rtsp_to_webrtc.client import get_adaptive_client
from rtsp_to_webrtc.exceptions import ClientError, ResponseError
from rtsp_to_webrtc.interface import WebRTCClientInterface

from homeassistant.components.camera import Camera
from homeassistant.components.camera.webrtc import (
    CameraWebRTCProvider,
    RTCIceServer,
    async_register_webrtc_provider,
    register_ice_server,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

_RTSP_PREFIXES = {"rtsp://", "rtsps://", "rtmp://"}

DOMAIN = "rtsp_to_webrtc"
DATA_SERVER_URL = "server_url"
DATA_UNSUB = "unsub"
TIMEOUT = 10
CONF_STUN_SERVER = "stun_server"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RTSPtoWebRTC from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client: WebRTCClientInterface
    try:
        async with asyncio.timeout(TIMEOUT):
            client = await get_adaptive_client(
                async_get_clientsession(hass), entry.data[DATA_SERVER_URL]
            )
    except ResponseError as err:
        raise ConfigEntryNotReady from err
    except (TimeoutError, ClientError) as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][CONF_STUN_SERVER] = entry.options.get(CONF_STUN_SERVER)
    if server := entry.options.get(CONF_STUN_SERVER):

        async def get_server() -> RTCIceServer:
            return RTCIceServer(urls=[server])

        entry.async_on_unload(register_ice_server(hass, get_server))

    provider = WebRTCProvider(client)
    entry.async_on_unload(async_register_webrtc_provider(hass, provider))
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


class WebRTCProvider(CameraWebRTCProvider):
    """WebRTC provider."""

    def __init__(self, client: WebRTCClientInterface) -> None:
        """Initialize the WebRTC provider."""
        self._client = client

    async def async_is_supported(self, stream_source: str) -> bool:
        """Return if this provider is supports the Camera as source."""
        return any(stream_source.startswith(prefix) for prefix in _RTSP_PREFIXES)

    async def async_handle_web_rtc_offer(
        self, camera: Camera, offer_sdp: str
    ) -> str | None:
        """Handle the WebRTC offer and return an answer."""
        if not (stream_source := await camera.stream_source()):
            return None
        stream_id = camera.entity_id
        try:
            async with asyncio.timeout(TIMEOUT):
                return await self._client.offer_stream_id(
                    stream_id, offer_sdp, stream_source
                )
        except TimeoutError as err:
            raise HomeAssistantError("Timeout talking to RTSPtoWebRTC server") from err
        except ClientError as err:
            raise HomeAssistantError(str(err)) from err


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DOMAIN in hass.data:
        del hass.data[DOMAIN]
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    if hass.data[DOMAIN][CONF_STUN_SERVER] != entry.options.get(CONF_STUN_SERVER):
        await hass.config_entries.async_reload(entry.entry_id)
