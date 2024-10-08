"""The go2rtc component."""

from collections.abc import Callable

from go2rtc_client import Go2RtcRestClient
from go2rtc_client.ws import (
    Go2RtcWsClient,
    ReceiveMessages,
    WebRTCCandidate,
    WebRTCOffer,
)

from homeassistant.components.camera import Camera
from homeassistant.components.camera.webrtc import (
    CameraWebRTCProvider,
    async_register_webrtc_provider,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
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
        server = Server(binary)
        entry.async_on_unload(server.stop)
        server.start()

    client = Go2RtcRestClient(async_get_clientsession(hass), entry.data[CONF_HOST])

    provider = WebRTCProvider(client, hass)
    entry.async_on_unload(async_register_webrtc_provider(hass, provider))
    return True


class WebRTCProvider(CameraWebRTCProvider):
    """WebRTC provider."""

    def __init__(self, rest_client: Go2RtcRestClient, hass: HomeAssistant) -> None:
        """Initialize the WebRTC provider."""
        self._rest_client = rest_client
        self._hass = hass
        self._sessions: dict[str, Go2RtcWsClient] = {}

    async def async_is_supported(self, stream_source: str) -> bool:
        """Return if this provider is supports the Camera as source."""
        return stream_source.partition(":")[0] in _SUPPORTED_STREAMS

    async def async_handle_web_rtc_offer(
        self,
        camera: Camera,
        offer_sdp: str,
        session_id: str,
        send_result: Callable[[dict], None],
    ) -> bool:
        """Handle the WebRTC offer and return the answer via the provided callback.

        Return value determines if the offer was handled successfully.
        """
        streams = await self._rest_client.streams.list()
        if camera.entity_id not in streams:
            if not (stream_source := await camera.stream_source()):
                return False
            await self._rest_client.streams.add(camera.entity_id, stream_source)

        self._sessions[session_id] = ws_client = Go2RtcWsClient(self._rest_client.host)

        @callback
        def on_messages(message: ReceiveMessages) -> None:
            """Handle messages."""
            send_result(message.to_dict())

        ws_client.subscribe(on_messages)
        await ws_client.send(WebRTCOffer(offer_sdp))

        return True

    async def async_on_webrtc_candidate(self, session_id: str, candidate: str) -> None:
        """Handle the WebRTC candidate."""

        if ws_client := self._sessions.get(session_id):
            await ws_client.send(WebRTCCandidate(candidate))
        else:
            raise ValueError("Unknown session")

    def close_session(self, session_id: str) -> None:
        """Close the session."""
        if ws_client := self._sessions.pop(session_id, None):
            self._hass.async_create_task(ws_client.close())


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
