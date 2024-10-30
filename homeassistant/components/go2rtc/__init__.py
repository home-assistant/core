"""The go2rtc component."""

import logging
import shutil

from go2rtc_client import Go2RtcRestClient
from go2rtc_client.ws import (
    Go2RtcWsClient,
    ReceiveMessages,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCOffer,
    WsError,
)
import voluptuous as vol

from homeassistant.components.camera import (
    Camera,
    CameraWebRTCProvider,
    WebRTCAnswer as HAWebRTCAnswer,
    WebRTCCandidate as HAWebRTCCandidate,
    WebRTCError,
    WebRTCMessage,
    WebRTCSendMessage,
    async_register_webrtc_provider,
)
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.package import is_docker_env

from .const import DOMAIN
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


CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Optional(CONF_URL): cv.url})},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up WebRTC."""
    url: str | None = None
    if not (configured_by_user := DOMAIN in config) or not (
        url := config[DOMAIN].get(CONF_URL)
    ):
        if not is_docker_env():
            if not configured_by_user:
                return True
            _LOGGER.warning("Go2rtc URL required in non-docker installs")
            return False
        if not (binary := await _get_binary(hass)):
            _LOGGER.error("Could not find go2rtc docker binary")
            return False

        # HA will manage the binary
        server = Server(hass, binary)
        await server.start()

        async def on_stop(event: Event) -> None:
            await server.stop()

        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, on_stop)

        url = "http://localhost:1984/"

    # Validate the server URL
    try:
        client = Go2RtcRestClient(async_get_clientsession(hass), url)
        await client.streams.list()
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Could not connect to go2rtc instance on %s", url)
        return False

    provider = WebRTCProvider(hass, url)
    async_register_webrtc_provider(hass, provider)
    return True


async def _get_binary(hass: HomeAssistant) -> str | None:
    """Return the binary path if found."""
    return await hass.async_add_executor_job(shutil.which, "go2rtc")


class WebRTCProvider(CameraWebRTCProvider):
    """WebRTC provider."""

    def __init__(self, hass: HomeAssistant, url: str) -> None:
        """Initialize the WebRTC provider."""
        self._hass = hass
        self._url = url
        self._session = async_get_clientsession(hass)
        self._rest_client = Go2RtcRestClient(self._session, url)
        self._sessions: dict[str, Go2RtcWsClient] = {}

    @property
    def domain(self) -> str:
        """Return the integration domain of the provider."""
        return DOMAIN

    @callback
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
            value: WebRTCMessage
            match message:
                case WebRTCCandidate():
                    value = HAWebRTCCandidate(message.candidate)
                case WebRTCAnswer():
                    value = HAWebRTCAnswer(message.sdp)
                case WsError():
                    value = WebRTCError("go2rtc_webrtc_offer_failed", message.error)

            send_message(value)

        ws_client.subscribe(on_messages)
        config = camera.async_get_webrtc_client_configuration()
        await ws_client.send(WebRTCOffer(offer_sdp, config.configuration.ice_servers))

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
