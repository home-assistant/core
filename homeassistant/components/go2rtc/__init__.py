"""The go2rtc component."""

from __future__ import annotations

import logging
import shutil

from aiohttp import ClientSession, web
from aiohttp.client_exceptions import ClientConnectionError, ServerConnectionError
from awesomeversion import AwesomeVersion
from go2rtc_client import Go2RtcRestClient
from go2rtc_client.exceptions import Go2RtcClientError, Go2RtcVersionError
from go2rtc_client.ws import (
    Go2RtcWsClient,
    ReceiveMessages,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCOffer,
    WsError,
)
import voluptuous as vol
from webrtc_models import RTCIceCandidateInit

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
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.default_config import DOMAIN as DEFAULT_CONFIG_DOMAIN
from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntry
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    discovery_flow,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.package import is_docker_env

from .const import (
    CONF_DEBUG_UI,
    DEBUG_UI_URL_MESSAGE,
    DOMAIN,
    GO2RTC_HLS_PROVIDER,
    HA_MANAGED_URL,
    RECOMMENDED_VERSION,
)
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
    {
        DOMAIN: vol.Schema(
            {
                vol.Exclusive(CONF_URL, DOMAIN, DEBUG_UI_URL_MESSAGE): cv.url,
                vol.Exclusive(CONF_DEBUG_UI, DOMAIN, DEBUG_UI_URL_MESSAGE): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_DATA_GO2RTC: HassKey[str] = HassKey(DOMAIN)
_RETRYABLE_ERRORS = (ClientConnectionError, ServerConnectionError)
type Go2RtcConfigEntry = ConfigEntry[WebRTCProvider]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up WebRTC."""
    url: str | None = None
    if DOMAIN not in config and DEFAULT_CONFIG_DOMAIN not in config:
        await _remove_go2rtc_entries(hass)
        return True

    if not (configured_by_user := DOMAIN in config) or not (
        url := config[DOMAIN].get(CONF_URL)
    ):
        if not is_docker_env():
            if not configured_by_user:
                # Remove config entry if it exists
                await _remove_go2rtc_entries(hass)
                return True
            _LOGGER.warning("Go2rtc URL required in non-docker installs")
            return False
        if not (binary := await _get_binary(hass)):
            _LOGGER.error("Could not find go2rtc docker binary")
            return False

        # HA will manage the binary
        server = Server(
            hass, binary, enable_ui=config.get(DOMAIN, {}).get(CONF_DEBUG_UI, False)
        )
        try:
            await server.start()
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Could not start go2rtc server", exc_info=True)
            return False

        async def on_stop(event: Event) -> None:
            await server.stop()

        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, on_stop)

        url = HA_MANAGED_URL

    hass.data[_DATA_GO2RTC] = url
    discovery_flow.async_create_flow(
        hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
    )
    return True


async def _remove_go2rtc_entries(hass: HomeAssistant) -> None:
    """Remove go2rtc config entries, if any."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_remove(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: Go2RtcConfigEntry) -> bool:
    """Set up go2rtc from a config entry."""

    url = hass.data[_DATA_GO2RTC]
    session = async_get_clientsession(hass)
    client = Go2RtcRestClient(session, url)
    # Validate the server URL
    try:
        version = await client.validate_server_version()
        if version < AwesomeVersion(RECOMMENDED_VERSION):
            ir.async_create_issue(
                hass,
                DOMAIN,
                "recommended_version",
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="recommended_version",
                translation_placeholders={
                    "recommended_version": RECOMMENDED_VERSION,
                    "current_version": str(version),
                },
            )
    except Go2RtcClientError as err:
        if isinstance(err.__cause__, _RETRYABLE_ERRORS):
            raise ConfigEntryNotReady(
                f"Could not connect to go2rtc instance on {url}"
            ) from err
        _LOGGER.warning("Could not connect to go2rtc instance on %s (%s)", url, err)
        return False
    except Go2RtcVersionError as err:
        raise ConfigEntryNotReady(
            f"The go2rtc server version is not supported, {err}"
        ) from err
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not connect to go2rtc instance on %s (%s)", url, err)
        return False

    webrtc_provider = WebRTCProvider(hass, url, session, client)
    hls_provider = Go2RtcHlsProvider(hass, url, session, client)
    
    # Set up HLS provider
    await hls_provider.async_setup()
    
    # Store both providers in runtime_data
    entry.runtime_data = webrtc_provider
    entry.async_on_unload(async_register_webrtc_provider(hass, webrtc_provider))
    
    # Store HLS provider for access in other parts of the integration
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["hls_provider"] = hls_provider
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Go2RtcConfigEntry) -> bool:
    """Unload a go2rtc config entry."""
    await entry.runtime_data.teardown()
    
    # Clean up HLS provider
    if DOMAIN in hass.data and "hls_provider" in hass.data[DOMAIN]:
        hls_provider = hass.data[DOMAIN]["hls_provider"]
        await hls_provider.async_teardown()
        del hass.data[DOMAIN]["hls_provider"]
        
    return True


async def _get_binary(hass: HomeAssistant) -> str | None:
    """Return the binary path if found."""
    return await hass.async_add_executor_job(shutil.which, "go2rtc")


class WebRTCProvider(CameraWebRTCProvider):
    """WebRTC provider."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        session: ClientSession,
        rest_client: Go2RtcRestClient,
    ) -> None:
        """Initialize the WebRTC provider."""
        self._hass = hass
        self._url = url
        self._session = session
        self._rest_client = rest_client
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
        try:
            await self._update_stream_source(camera)
        except HomeAssistantError as err:
            send_message(WebRTCError("go2rtc_webrtc_offer_failed", str(err)))
            return

        self._sessions[session_id] = ws_client = Go2RtcWsClient(
            self._session, self._url, source=camera.entity_id
        )

        @callback
        def on_messages(message: ReceiveMessages) -> None:
            """Handle messages."""
            value: WebRTCMessage
            match message:
                case WebRTCCandidate():
                    value = HAWebRTCCandidate(RTCIceCandidateInit(message.candidate))
                case WebRTCAnswer():
                    value = HAWebRTCAnswer(message.sdp)
                case WsError():
                    value = WebRTCError("go2rtc_webrtc_offer_failed", message.error)

            send_message(value)

        ws_client.subscribe(on_messages)
        config = camera.async_get_webrtc_client_configuration()
        await ws_client.send(WebRTCOffer(offer_sdp, config.configuration.ice_servers))

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle the WebRTC candidate."""

        if ws_client := self._sessions.get(session_id):
            await ws_client.send(WebRTCCandidate(candidate.candidate))
        else:
            _LOGGER.debug("Unknown session %s. Ignoring candidate", session_id)

    @callback
    def async_close_session(self, session_id: str) -> None:
        """Close the session."""
        ws_client = self._sessions.pop(session_id)
        self._hass.async_create_task(ws_client.close())

    async def async_get_image(
        self,
        camera: Camera,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Get an image from the camera."""
        await self._update_stream_source(camera)
        return await self._rest_client.get_jpeg_snapshot(
            camera.entity_id, width, height
        )

    async def _update_stream_source(self, camera: Camera) -> None:
        """Update the stream source in go2rtc config if needed."""
        if not (stream_source := await camera.stream_source()):
            await self.teardown()
            raise HomeAssistantError("Camera has no stream source")

        if camera.platform.platform_name == "generic":
            # This is a workaround to use ffmpeg for generic cameras
            # A proper fix will be added in the future together with supporting multiple streams per camera
            stream_source = "ffmpeg:" + stream_source

        if not self.async_is_supported(stream_source):
            await self.teardown()
            raise HomeAssistantError("Stream source is not supported by go2rtc")

        streams = await self._rest_client.streams.list()

        if (stream := streams.get(camera.entity_id)) is None or not any(
            stream_source == producer.url for producer in stream.producers
        ):
            await self._rest_client.streams.add(
                camera.entity_id,
                [
                    stream_source,
                    # We are setting any ffmpeg rtsp related logs to debug
                    # Connection problems to the camera will be logged by the first stream
                    # Therefore setting it to debug will not hide any important logs
                    f"ffmpeg:{camera.entity_id}#audio=opus#query=log_level=debug",
                ],
            )

    async def teardown(self) -> None:
        """Tear down the provider."""
        for ws_client in self._sessions.values():
            await ws_client.close()
        self._sessions.clear()


class Go2RtcHlsView(HomeAssistantView):
    """View to proxy HLS requests to go2rtc server."""

    url = r"/api/go2rtc_hls/{entity_id}/{file_name:.*}"
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
        
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        session = async_get_clientsession(self.hass)
        
        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise web.HTTPNotFound()
                
                content_type = resp.headers.get('Content-Type', 'application/vnd.apple.mpegurl')
                body = await resp.read()
                
                # For playlist files, we need to rewrite segment URLs to point to our proxy
                if file_name == "playlist.m3u8" and content_type.startswith('application/'):
                    content = body.decode('utf-8')
                    # Rewrite segment URLs to use our proxy
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line and not line.startswith('#') and not line.startswith('http'):
                            # This is a segment reference, rewrite it to use our proxy
                            lines[i] = f"/api/go2rtc_hls/{entity_id}/{line}"
                    body = '\n'.join(lines).encode('utf-8')
                
                return web.Response(
                    body=body,
                    content_type=content_type,
                    headers={'Access-Control-Allow-Origin': '*'}
                )
        except Exception as err:
            _LOGGER.error("Error proxying HLS request to go2rtc: %s", err)
            raise web.HTTPInternalServerError() from err


class Go2RtcHlsProvider:
    """Go2rtc HLS provider for camera streaming."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        session: ClientSession,
        rest_client: Go2RtcRestClient,
    ) -> None:
        """Initialize the HLS provider."""
        self._hass = hass
        self._url = url
        self._session = session
        self._rest_client = rest_client
        self._view: Go2RtcHlsView | None = None
        
    async def async_setup(self) -> None:
        """Set up the HLS provider."""
        # Register the HLS view for proxying requests
        self._view = Go2RtcHlsView(self._hass, self._url)
        self._hass.http.register_view(self._view)
        
    async def async_teardown(self) -> None:
        """Tear down the HLS provider."""
        # View cleanup is handled by Home Assistant
        pass

    @callback
    def async_is_supported(self, stream_source: str) -> bool:
        """Return if this provider supports the camera stream source."""
        return stream_source.partition(":")[0] in _SUPPORTED_STREAMS

    async def async_get_stream_url(self, camera: Camera) -> str:
        """Get HLS stream URL for the camera."""
        # Ensure stream is configured in go2rtc
        await self._update_stream_source(camera)
        
        # Return the HLS playlist URL through our proxy
        return f"/api/go2rtc_hls/{camera.entity_id}/playlist.m3u8"

    async def _update_stream_source(self, camera: Camera) -> None:
        """Update the stream source in go2rtc config if needed."""
        if not (stream_source := await camera.stream_source()):
            raise HomeAssistantError("Camera has no stream source")

        if camera.platform.platform_name == "generic":
            # This is a workaround to use ffmpeg for generic cameras
            # A proper fix will be added in the future together with supporting multiple streams per camera
            stream_source = "ffmpeg:" + stream_source

        if not self.async_is_supported(stream_source):
            raise HomeAssistantError("Stream source is not supported by go2rtc")

        streams = await self._rest_client.streams.list()

        if (stream := streams.get(camera.entity_id)) is None or not any(
            stream_source == producer.url for producer in stream.producers
        ):
            await self._rest_client.streams.add(
                camera.entity_id,
                [
                    stream_source,
                    # We are setting any ffmpeg rtsp related logs to debug
                    # Connection problems to the camera will be logged by the first stream
                    # Therefore setting it to debug will not hide any important logs
                    f"ffmpeg:{camera.entity_id}#audio=opus#query=log_level=debug",
                ],
            )
