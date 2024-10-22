"""The go2rtc component."""

import logging

from go2rtc_client import Go2RtcRestClient
from go2rtc_client.ws import (
    Go2RtcWsClient,
    ReceiveMessages,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCOffer,
    WsError,
)

from homeassistant.components.camera import Camera
from homeassistant.components.camera.webrtc import (
    CameraWebRTCProvider,
    WebRTCAnswer as HAWebRTCAnswer,
    WebRTCCandidate as HAWebRTCCandidate,
    WebRTCError,
    WebRTCMessages,
    WebRTCSendMessage,
    async_register_webrtc_provider,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_BINARY
from .server import Server

_LOGGER = logging.getLogger(__name__)

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

    provider = WebRTCProvider(hass, entry.data[CONF_URL])
    entry.async_on_unload(async_register_webrtc_provider(hass, provider))
    return True


class WebRTCProvider(CameraWebRTCProvider):
    """WebRTC provider."""

    def __init__(self, hass: HomeAssistant, url: str) -> None:
        """Initialize the WebRTC provider."""
        self._hass = hass
        self._url = url
        self._session = async_get_clientsession(hass)
        self._rest_client = Go2RtcRestClient(self._session, url)
        self._sessions: dict[str, Go2RtcWsClient] = {}

    def async_is_supported(self, stream_source: str) -> bool:
        """Return if this provider is supports the Camera as source."""
        return stream_source.partition(":")[0] in _SUPPORTED_STREAMS

    async def async_handle_async_webrtc_offer(
        self,
        camera: Camera,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
    ) -> None:
        """Handle the WebRTC offer and return the answer via the provided callback."""
        self._sessions[session_id] = ws_client = Go2RtcWsClient(
            self._session, self._url, source=camera.entity_id
        )

        streams = await self._rest_client.streams.list()
        if camera.entity_id not in streams:
            if not (stream_source := await camera.stream_source()):
                send_message(
                    WebRTCError(
                        "go2rtc_webrtc_offer_failed", "Camera has no stream source"
                    )
                )
                return
            await self._rest_client.streams.add(camera.entity_id, stream_source)

        @callback
        def on_messages(message: ReceiveMessages) -> None:
            """Handle messages."""
            value: WebRTCMessages
            match message:
                case WebRTCCandidate():
                    value = HAWebRTCCandidate(message.candidate)
                case WebRTCAnswer():
                    value = HAWebRTCAnswer(message.answer)
                case WsError():
                    value = WebRTCError("go2rtc_webrtc_offer_failed", message.error)
                case _:
                    _LOGGER.warning("Unknown message %s", message)
                    return

            send_message(value)

        ws_client.subscribe(on_messages)
        await ws_client.send(WebRTCOffer(offer_sdp))

    async def async_on_webrtc_candidate(self, session_id: str, candidate: str) -> None:
        """Handle the WebRTC candidate."""

        if ws_client := self._sessions.get(session_id):
            await ws_client.send(WebRTCCandidate(candidate))
        else:
            _LOGGER.debug("Unknown session %s. Ignoring candidate", session_id)

    @callback
    def async_close_session(self, session_id: str) -> None:
        """Close the session."""
        ws_client = self._sessions.pop(session_id)
        self._hass.async_create_task(ws_client.close())


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
