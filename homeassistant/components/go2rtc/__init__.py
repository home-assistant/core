"""The go2rtc component."""

from go2rtc_client import Go2RtcClient, WebRTCSdpOffer

from homeassistant.components.camera import Camera
from homeassistant.components.camera.webrtc import (
    CameraWebRTCProvider,
    async_register_webrtc_provider,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_BINARY
from .server import Server

_SUPPORTED_STREAMS = frozenset(
    (
        "bubble",
        "dvrip",
        "expr",
        "ffmpeg",
        "gopro",
        "homekit",
        "http",
        "https",
        "httpx",
        "isapi",
        "ivideon",
        "kasa",
        "nest",
        "onvif",
        "roborock",
        "rtmp",
        "rtmps",
        "rtmpx",
        "rtsp",
        "rtsps",
        "rtspx",
        "tapo",
        "tcp",
        "webrtc",
        "webtorrent",
    )
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WebRTC from a config entry."""
    if binary := entry.data.get(CONF_BINARY):
        # HA will manage the binary
        server = Server(hass, binary)

        entry.async_on_unload(server.stop)
        await server.start()

    client = Go2RtcClient(async_get_clientsession(hass), entry.data[CONF_HOST])

    provider = WebRTCProvider(client)
    entry.async_on_unload(async_register_webrtc_provider(hass, provider))
    return True


class WebRTCProvider(CameraWebRTCProvider):
    """WebRTC provider."""

    def __init__(self, client: Go2RtcClient) -> None:
        """Initialize the WebRTC provider."""
        self._client = client

    async def async_is_supported(self, stream_source: str) -> bool:
        """Return if this provider is supports the Camera as source."""
        return stream_source.partition(":")[0] in _SUPPORTED_STREAMS

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
