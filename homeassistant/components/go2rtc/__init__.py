"""The go2rtc component."""

from homeassistant.components.camera import Camera
from homeassistant.components.camera.webrtc import (
    CameraWebRTCProvider,
    async_register_webrtc_provider,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import utils
from .api.client import Go2rtcClient
from .api.models import WebRTCSdpOffer
from .utils import Server

type WebRTCConfigEntry = ConfigEntry[Server]


async def async_setup_entry(hass: HomeAssistant, entry: WebRTCConfigEntry) -> bool:
    """Set up WebRTC from a config entry."""
    # todo
    binary = await utils.validate_binary(hass)
    if not binary:
        return False

    server = Server(binary)
    entry.async_on_unload(server.stop)
    entry.runtime_data = server
    server.start()

    client = Go2rtcClient(async_get_clientsession(hass), server.url)

    provider = WebRTCProvider(entry, client)
    entry.async_on_unload(async_register_webrtc_provider(hass, provider))
    return True


class WebRTCProvider(CameraWebRTCProvider):
    """WebRTC provider."""

    def __init__(self, entry: ConfigEntry, client: Go2rtcClient) -> None:
        """Initialize the WebRTC provider."""
        self._entry = entry
        self._client = client

    async def async_is_supported(self, stream_source: str) -> bool:
        """Return if this provider is supports the Camera as source."""
        return any(
            stream_source.startswith(prefix)
            for prefix in ("rtsp://", "rtsps://", "rtmp://")
        )
        # todo

    async def async_handle_web_rtc_offer(
        self, camera: Camera, offer_sdp: str
    ) -> str | None:
        """Handle the WebRTC offer and return an answer."""
        streams = await self._client.streams.list()
        if camera.entity_id not in streams:
            if not (stream_source := await camera.stream_source()):
                return None
            await self._client.streams.add(camera.entity_id, stream_source)

        answer = await self._client.webrtc.forward_whep_sdp_offer(
            camera.entity_id, WebRTCSdpOffer(offer_sdp)
        )
        return answer.sdp


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
