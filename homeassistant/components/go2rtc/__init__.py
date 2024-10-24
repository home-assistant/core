"""The go2rtc component."""

import logging
import shutil

from go2rtc_client import Go2RtcClient, WebRTCSdpOffer
import voluptuous as vol

from homeassistant.components.camera import Camera
from homeassistant.components.camera.webrtc import (
    CameraWebRTCProvider,
    async_register_webrtc_provider,
)
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
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


CONFIG_SCHEMA = vol.Schema({DOMAIN: {vol.Optional(CONF_URL): cv.url}})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up WebRTC."""
    url: str | None = None
    if not (url := config[DOMAIN].get(CONF_URL)):
        if not is_docker_env():
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

    if url is None:
        url = "http://localhost:1984/"

    # Validate the server URL
    try:
        client = Go2RtcClient(async_get_clientsession(hass), url)
        await client.streams.list()
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Could not connect to go2rtc instance on %s", url)
        return False

    client = Go2RtcClient(async_get_clientsession(hass), url)

    provider = WebRTCProvider(client)
    async_register_webrtc_provider(hass, provider)
    return True


async def _get_binary(hass: HomeAssistant) -> str | None:
    """Return the binary path if found."""
    return await hass.async_add_executor_job(shutil.which, "go2rtc")


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
