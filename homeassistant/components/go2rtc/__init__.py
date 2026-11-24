"""The go2rtc component."""

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
import logging
import re
from secrets import token_hex
import shutil
from tempfile import mkdtemp
from typing import override
from urllib.parse import quote

from aiohttp import ClientSession, UnixConnector, encode_basic_auth
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
import probatio
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
    get_dynamic_camera_stream_settings,
)
from homeassistant.components.default_config import DOMAIN as DEFAULT_CONFIG_DOMAIN
from homeassistant.components.stream import Orientation
from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import (
    config_validation as cv,
    discovery_flow,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.package import is_docker_env

from .const import (
    CONF_DEBUG_UI,
    DEBUG_UI_URL_MESSAGE,
    DOMAIN,
    HA_MANAGED_RTSP_PORT,
    HA_MANAGED_URL,
    RECOMMENDED_VERSION,
    SIGNAL_SERVER_RESTARTED,
)
from .server import Server
from .util import get_camera_identifier, get_go2rtc_unix_socket_path

_LOGGER = logging.getLogger(__name__)

_FFMPEG = "ffmpeg"
_AUTH = "auth"
# Mirrors go2rtc 1.9.15+, which masks the userinfo of URLs in its API responses
_USERINFO = re.compile(r"://[A-Za-z0-9\-._~!$&'()*+,;=%:]+@")


def _validate_auth(config: dict) -> dict:
    """Validate username/password only when URL is configured or debug UI enabled."""
    auth_exists = CONF_USERNAME in config
    debug_ui_enabled = config.get(CONF_DEBUG_UI, False)

    if debug_ui_enabled and not auth_exists:
        raise probatio.Invalid(
            "Username and password must be set when debug_ui is true"
        )

    if auth_exists and CONF_URL not in config and not debug_ui_enabled:
        raise probatio.Invalid(
            "Username and password can only be set when a URL is"
            " configured or debug_ui is true"
        )

    return config


CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.All(
            probatio.Schema(
                {
                    probatio.Exclusive(CONF_URL, DOMAIN, DEBUG_UI_URL_MESSAGE): cv.url,
                    probatio.Exclusive(
                        CONF_DEBUG_UI, DOMAIN, DEBUG_UI_URL_MESSAGE
                    ): cv.boolean,
                    probatio.Inclusive(CONF_USERNAME, _AUTH): probatio.All(
                        cv.string, probatio.NonEmpty()
                    ),
                    probatio.Inclusive(
                        probatio.Secret(CONF_PASSWORD), _AUTH
                    ): probatio.All(cv.string, probatio.NonEmpty()),
                }
            ),
            _validate_auth,
        )
    },
    extra=probatio.ALLOW_EXTRA,
)

_DATA_GO2RTC: HassKey[Go2RtcConfig] = HassKey(DOMAIN)
_RETRYABLE_ERRORS = (ClientConnectionError, ServerConnectionError)
# Seconds before each retry of restoring the restreams, the last repeating
_RESTORE_RETRY_DELAYS = (5, 15, 30, 60, 300)
type Go2RtcConfigEntry = ConfigEntry[WebRTCProvider]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up WebRTC."""
    url: str | None = None
    username: str | None = None
    password: str | None = None
    managed = False

    if DOMAIN not in config and DEFAULT_CONFIG_DOMAIN not in config:
        await _remove_go2rtc_entries(hass)
        return True

    domain_config = config.get(DOMAIN, {})
    username = domain_config.get(CONF_USERNAME)
    password = domain_config.get(CONF_PASSWORD)

    if not (configured_by_user := DOMAIN in config) or not (
        url := domain_config.get(CONF_URL)
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

        # Generate random credentials when not provided to secure the server
        if not username or not password:
            username = token_hex()
            password = token_hex()
            _LOGGER.debug("Generated random credentials for go2rtc server")

        # HA will manage the binary
        temp_dir = mkdtemp(prefix="go2rtc-")
        # Manually created session (not using the helper) needs to be closed manually
        # See on_stop listener below
        session = ClientSession(
            connector=UnixConnector(path=get_go2rtc_unix_socket_path(temp_dir)),
            headers={"Authorization": encode_basic_auth(username, password)},
        )
        server = Server(
            hass,
            binary,
            session,
            enable_ui=domain_config.get(CONF_DEBUG_UI, False),
            username=username,
            password=password,
            working_dir=temp_dir,
        )
        try:
            await server.start()
        except Exception:
            _LOGGER.warning("Could not start go2rtc server", exc_info=True)
            await session.close()
            return False

        async def on_stop(event: Event) -> None:
            await server.stop()
            await session.close()

        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, on_stop)

        url = HA_MANAGED_URL
        managed = True
    elif username and password:
        session = async_create_clientsession(
            hass, headers={"Authorization": encode_basic_auth(username, password)}
        )
    else:
        session = async_get_clientsession(hass)

    hass.data[_DATA_GO2RTC] = Go2RtcConfig(url, session, managed)
    discovery_flow.async_create_flow(
        hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
    )
    return True


async def _remove_go2rtc_entries(hass: HomeAssistant) -> None:
    """Remove go2rtc config entries, if any."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_remove(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: Go2RtcConfigEntry) -> None:
    """Set up go2rtc from a config entry."""

    config = hass.data[_DATA_GO2RTC]
    url = config.url
    session = config.session
    client = Go2RtcRestClient(session, url)
    # Validate the server URL
    try:
        version = await client.validate_server_version()
        if version < AwesomeVersion(RECOMMENDED_VERSION):
            ir.async_create_issue(
                hass,
                DOMAIN,
                "recommended_version",
                config_entry_id=entry.entry_id,
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
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"url": url},
        ) from err
    except Go2RtcVersionError as err:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "unsupported_version",
            config_entry_id=entry.entry_id,
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="unsupported_version",
            translation_placeholders={"error": str(err)},
        )
        raise ConfigEntryNotReady(
            f"The go2rtc server version is not supported, {err}"
        ) from err
    except Exception as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"url": url},
        ) from err

    ir.async_delete_issue(hass, DOMAIN, "unsupported_version")

    provider = entry.runtime_data = WebRTCProvider(
        hass, url, session, client, managed=config.managed
    )
    await provider.initialize()
    entry.async_on_unload(async_register_webrtc_provider(hass, provider))
    if config.managed:
        entry.async_on_unload(
            async_dispatcher_connect(
                hass, SIGNAL_SERVER_RESTARTED, provider.async_restore_restreams
            )
        )


async def async_unload_entry(hass: HomeAssistant, entry: Go2RtcConfigEntry) -> None:
    """Unload a go2rtc config entry."""
    await entry.runtime_data.teardown()


async def _get_binary(hass: HomeAssistant) -> str | None:
    """Return the binary path if found."""
    return await hass.async_add_executor_job(shutil.which, "go2rtc")


@dataclass(frozen=True)
class _SessionInfo:
    """Session info."""

    ws_client: Go2RtcWsClient
    camera: Camera


class WebRTCProvider(CameraWebRTCProvider):
    """WebRTC provider."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        session: ClientSession,
        rest_client: Go2RtcRestClient,
        *,
        managed: bool = False,
    ) -> None:
        """Initialize the WebRTC provider."""
        self._hass = hass
        self._url = url
        self._managed = managed
        self._session = session
        self._rest_client = rest_client
        self._sessions: dict[str, _SessionInfo] = {}
        self._supported_schemes: set[str] = set()
        self._added_stream_sources: dict[str, str] = {}
        self._restreamed_cameras: dict[str, Camera] = {}
        self._restore_attempt = 0
        self._restore_task: asyncio.Task[None] | None = None
        self._cancel_restore_retry: CALLBACK_TYPE | None = None

    @property
    @override
    def domain(self) -> str:
        """Return the integration domain of the provider."""
        return DOMAIN

    async def initialize(self) -> None:
        """Initialize the provider."""
        self._supported_schemes = await self._rest_client.schemes.list()

    @callback
    @override
    def async_is_supported(self, stream_source: str) -> bool:
        """Return if this provider is supports the Camera as source."""
        return stream_source.partition(":")[0] in self._supported_schemes

    @override
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
        except Go2RtcClientError:
            # Not logged, as the client error can contain the stream source
            # with its credentials
            send_message(
                WebRTCError(
                    "go2rtc_webrtc_offer_failed",
                    "Unable to update the stream in go2rtc",
                )
            )
            return

        ws_client = Go2RtcWsClient(
            self._session, self._url, source=get_camera_identifier(camera)
        )
        self._sessions[session_id] = _SessionInfo(
            ws_client=ws_client,
            camera=camera,
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

    @override
    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle the WebRTC candidate."""

        if session_info := self._sessions.get(session_id):
            await session_info.ws_client.send(WebRTCCandidate(candidate.candidate))
        else:
            _LOGGER.debug("Unknown session %s. Ignoring candidate", session_id)

    @callback
    @override
    def async_close_session(self, session_id: str) -> None:
        """Close the session."""
        if session_info := self._sessions.pop(session_id, None):
            self._hass.async_create_task(session_info.ws_client.close())

    @override
    async def async_get_image(
        self,
        camera: Camera,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Get an image from the camera."""
        try:
            await self._update_stream_source(camera)
            return await self._rest_client.get_jpeg_snapshot(
                get_camera_identifier(camera), width, height
            )
        except Go2RtcClientError as err:
            raise HomeAssistantError("Unable to get image from go2rtc") from err

    @callback
    @override
    def async_supports_stream_source(self, camera: Camera) -> bool:
        """Return if go2rtc can restream the camera, see async_get_stream_source."""
        return self._managed

    @override
    async def async_get_stream_source(self, camera: Camera) -> str | None:
        """Return go2rtc's RTSP restream of a camera without a stream source.

        Only the go2rtc server Home Assistant manages has a known RTSP address.
        The restream carries AAC audio, which HLS needs.
        """
        if not self._managed:
            return None
        try:
            await self._update_stream_source(camera)
        except Go2RtcClientError:
            # Without the client error, which can carry the source's credentials
            raise HomeAssistantError("Unable to update the stream in go2rtc") from None
        identifier = get_camera_identifier(camera)
        # A restarted server has lost the stream, but HLS and recording keep
        # reading its address
        self._restreamed_cameras[identifier] = camera
        return (
            f"rtsp://127.0.0.1:{HA_MANAGED_RTSP_PORT}/"
            f"{quote(identifier, safe='')}?video&audio=aac"
        )

    @callback
    def async_restore_restreams(self) -> None:
        """Restore the restreams after the managed server restarted."""
        self._restore_attempt = 0
        self._start_restore()

    @callback
    def _async_retry_restore(self, _now: datetime) -> None:
        """Retry restoring the restreams."""
        self._cancel_restore_retry = None
        self._start_restore()

    @callback
    def _start_restore(self) -> None:
        """Start restoring the restreams, in place of any earlier attempt."""
        self._stop_restore()
        self._restore_task = self._hass.async_create_task(
            self._async_restore_restreams(), "go2rtc restore restreams"
        )

    @callback
    def _stop_restore(self) -> None:
        """Cancel a running or pending attempt to restore the restreams."""
        if self._cancel_restore_retry:
            self._cancel_restore_retry()
            self._cancel_restore_retry = None
        if self._restore_task:
            self._restore_task.cancel()
            self._restore_task = None

    async def _async_restore_restreams(self) -> None:
        """Add the restreamed cameras' streams again to a restarted server.

        HLS and recording keep reading the restreams without asking for them
        again, so a failure is retried until it succeeds.
        """
        failed: list[str] = []
        for identifier, camera in list(self._restreamed_cameras.items()):
            if identifier not in self._restreamed_cameras:
                # Unregistered while an earlier camera was restored
                continue
            try:
                await self._update_stream_source(camera)
            except Go2RtcClientError, HomeAssistantError:
                # Not logged, as the error can carry the source's credentials
                failed.append(camera.entity_id)
        if not failed:
            self._restore_task = None
            if self._restore_attempt:
                _LOGGER.info("Restored the restreams in go2rtc")
            self._restore_attempt = 0
            return
        if not self._restore_attempt:
            _LOGGER.warning(
                "Unable to restore the restreams of %s in go2rtc, retrying",
                ", ".join(failed),
            )
        delay = _RESTORE_RETRY_DELAYS[
            min(self._restore_attempt, len(_RESTORE_RETRY_DELAYS) - 1)
        ]
        self._restore_attempt += 1
        self._restore_task = None
        self._cancel_restore_retry = async_call_later(
            self._hass, delay, self._async_retry_restore
        )

    async def _update_stream_source(self, camera: Camera) -> None:
        """Update the stream source in go2rtc config if needed."""
        # Resolve each source once, as stream_source can be slow (e.g. it asks
        # the camera for its URLs) and is the default webrtc_source
        ffmpeg_source = await camera.stream_source()
        if getattr(camera.webrtc_source, "__func__", None) is Camera.webrtc_source:
            stream_source = ffmpeg_source
        else:
            stream_source = await camera.webrtc_source()
        if not stream_source:
            await self._close_camera_sessions(camera)
            raise HomeAssistantError("Camera has no stream source")
        # A source native to go2rtc, which FFmpeg can't open
        native_source = stream_source != ffmpeg_source

        if camera.platform.platform_name == "generic":
            # This is a workaround to use ffmpeg for generic cameras
            # A proper fix will be added in the future together
            # with supporting multiple streams per camera
            stream_source = "ffmpeg:" + stream_source

        if not self.async_is_supported(stream_source):
            await self._close_camera_sessions(camera)
            raise HomeAssistantError("Stream source is not supported by go2rtc")

        camera_prefs = await get_dynamic_camera_stream_settings(
            self._hass, camera.entity_id
        )
        # FFmpeg applies the orientation, so live view of a native source
        # isn't transformed
        if (
            camera_prefs.orientation is not Orientation.NO_TRANSFORM
            and not native_source
        ):
            # Camera orientation manually set by user
            if not stream_source.startswith(_FFMPEG):
                stream_source = _FFMPEG + ":" + stream_source
            stream_source += "#video=h264#audio=copy"
            match camera_prefs.orientation:
                case Orientation.MIRROR:
                    stream_source += "#raw=-vf hflip"
                case Orientation.ROTATE_180:
                    stream_source += "#rotate=180"
                case Orientation.FLIP:
                    stream_source += "#raw=-vf vflip"
                case Orientation.ROTATE_LEFT_AND_FLIP:
                    # Cannot use any filter when using raw one
                    stream_source += "#raw=-vf transpose=2,vflip"
                case Orientation.ROTATE_LEFT:
                    stream_source += "#rotate=-90"
                case Orientation.ROTATE_RIGHT_AND_FLIP:
                    # Cannot use any filter when using raw one
                    stream_source += "#raw=-vf transpose=1,vflip"
                case Orientation.ROTATE_RIGHT:
                    stream_source += "#rotate=90"

        identifier = get_camera_identifier(camera)
        sources = [
            stream_source,
            # We are setting any ffmpeg rtsp related logs to debug
            # Connection problems to the camera will be
            # logged by the first stream
            # Therefore setting it to debug will not hide any important logs
            f"ffmpeg:{identifier}#audio=opus#query=log_level=debug",
        ]
        if ffmpeg_source is None:
            # FFmpeg reads go2rtc's restream instead (async_get_stream_source),
            # with AAC audio transcoded only while someone reads it
            sources.append(f"ffmpeg:{identifier}#audio=aac#query=log_level=debug")

        streams = await self._rest_client.streams.list()

        if (stream := streams.get(identifier)) is None or not any(
            self._is_added_stream_source(identifier, stream_source, producer.url)
            for producer in stream.producers
        ):
            await self._rest_client.streams.add(identifier, sources)
            self._added_stream_sources[identifier] = stream_source

    def _is_added_stream_source(
        self, identifier: str, stream_source: str, producer_url: str
    ) -> bool:
        if producer_url == stream_source:
            return True

        # A masked URL hides credential changes, so it only counts when it
        # belongs to the source we added last
        if self._added_stream_sources.get(identifier) != stream_source:
            return False

        return producer_url == _USERINFO.sub("://***@", stream_source)

    async def _update_preload_stream(self, camera: Camera) -> None:
        identifier = get_camera_identifier(camera)
        camera_prefs = await get_dynamic_camera_stream_settings(
            self._hass, camera.entity_id
        )
        preload_streams = await self._rest_client.preload.list()

        if camera_prefs.preload_stream == (identifier in preload_streams):
            return

        if camera_prefs.preload_stream:
            # We need to first add the stream source otherwise preload enabling will fail
            await self._update_stream_source(camera)
            await self._rest_client.preload.enable(identifier)
        else:
            await self._rest_client.preload.disable(identifier)

    async def _close_camera_sessions(self, camera: Camera) -> None:
        for session_id in list(self._sessions):
            session_info = self._sessions.get(session_id)
            if session_info is None or session_info.camera != camera:
                continue
            # Unregister before closing, as closing yields to the event loop
            del self._sessions[session_id]
            await session_info.ws_client.close()

    async def teardown(self) -> None:
        """Tear down the provider."""
        task = self._restore_task
        self._stop_restore()
        if task:
            with suppress(asyncio.CancelledError):
                await task
        while self._sessions:
            _, session_info = self._sessions.popitem()
            await session_info.ws_client.close()

    @override
    async def async_register_camera(
        self,
        camera: Camera,
    ) -> None:
        """Will be called when the provider is registered for a camera."""
        await self._update_preload_stream(camera)

    @override
    async def async_unregister_camera(
        self,
        camera: Camera,
    ) -> None:
        """Will be called when the provider is unregistered for a camera."""
        await self._close_camera_sessions(camera)
        identifier = get_camera_identifier(camera)
        self._added_stream_sources.pop(identifier, None)
        self._restreamed_cameras.pop(identifier, None)
        if identifier in await self._rest_client.preload.list():
            await self._rest_client.preload.disable(identifier)

    @override
    async def async_on_camera_prefs_update(
        self,
        camera: Camera,
    ) -> None:
        """Will be called when the camera preferences are updated."""
        await self._update_preload_stream(camera)


@dataclass
class Go2RtcConfig:
    """Go2rtc configuration."""

    url: str
    session: ClientSession
    managed: bool = False
