"""Support for Google Nest SDM Cameras."""

from abc import ABC
import asyncio
from collections.abc import Awaitable, Callable
import datetime as dt
import functools
import logging
from pathlib import Path
from typing import Any, cast, override
from urllib.parse import urlencode

from google_nest_sdm.camera_traits import (
    CameraLiveStreamTrait,
    RtspStream,
    StreamingProtocol,
    WebRtcStream,
)
from google_nest_sdm.device import Device
from google_nest_sdm.exceptions import ApiException, FailedPreconditionException
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    CameraWebRTCProvider,
    WebRTCAnswer,
    WebRTCClientConfiguration,
    WebRTCSendMessage,
)
from homeassistant.components.stream import CONF_EXTRA_PART_WAIT_TIME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from .api import AsyncConfigEntryAuth
from .const import CONF_WEBRTC_SNAPSHOTS, DOMAIN
from .device_info import NestDeviceInfo
from .types import NestConfigEntry

_LOGGER = logging.getLogger(__name__)

PLACEHOLDER = Path(__file__).parent / "placeholder.png"

# Used to schedule an alarm to refresh the stream before expiration
STREAM_EXPIRATION_BUFFER = dt.timedelta(seconds=30)

# Refresh streams with a bounded interval and backoff on failure
MIN_REFRESH_BACKOFF_INTERVAL = dt.timedelta(minutes=1)
MAX_REFRESH_BACKOFF_INTERVAL = dt.timedelta(minutes=10)
BACKOFF_MULTIPLIER = 1.5

# A snapshot fetched over WebRTC is reused for this long, so that repeated
# requests don't each open a new session to the camera. Each new session is a
# GenerateWebRtcStream command. Google's published limit for Sandbox projects
# is 100 commands an hour per camera, counted across all Device Access
# projects, so a shorter cache can leave other apps that use the camera too
# few for live view.
SNAPSHOT_CACHE_DURATION = dt.timedelta(minutes=2)
# After a failed fetch, wait this long before trying again, doubling the wait
# after each further failure up to the maximum
SNAPSHOT_MIN_RETRY_INTERVAL = dt.timedelta(seconds=15)
SNAPSHOT_MAX_RETRY_INTERVAL = dt.timedelta(minutes=5)
# Abandon a fetch that takes longer than this
SNAPSHOT_FETCH_TIMEOUT = 30


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the cameras."""
    snapshot_auth: AsyncConfigEntryAuth | None = None
    if entry.options.get(CONF_WEBRTC_SNAPSHOTS):
        snapshot_auth = entry.runtime_data.auth

    def devices_added(devices: list[Device]) -> None:
        entities: list[NestCameraBaseEntity] = []
        for device in devices:
            if (live_stream := device.traits.get(CameraLiveStreamTrait.NAME)) is None:
                continue
            if StreamingProtocol.WEB_RTC in live_stream.supported_protocols:
                entities.append(NestWebRTCEntity(device, snapshot_auth))
            elif StreamingProtocol.RTSP in live_stream.supported_protocols:
                entities.append(NestRTSPEntity(device))

        async_add_entities(entities)

    entry.runtime_data.register_devices_listener(devices_added)


class StreamRefresh:
    """Class that will refresh an expiring stream.

    This class will schedule an alarm for the next expiration time of a stream.
    When the alarm fires, it runs the provided `refresh_cb` to extend the
    lifetime of the stream and return a new expiration time.

    A simple backoff will be applied when the refresh callback fails.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        expires_at: dt.datetime,
        refresh_cb: Callable[[], Awaitable[dt.datetime | None]],
    ) -> None:
        """Initialize StreamRefresh."""
        self._hass = hass
        self._unsub: Callable[[], None] | None = None
        self._min_refresh_interval = MIN_REFRESH_BACKOFF_INTERVAL
        self._refresh_cb = refresh_cb
        self._schedule_stream_refresh(expires_at - STREAM_EXPIRATION_BUFFER)

    def unsub(self) -> None:
        """Invalidates the stream."""
        if self._unsub:
            self._unsub()

    async def _handle_refresh(self, _: dt.datetime) -> None:
        """Alarm that fires to check if the stream should be refreshed."""
        self._unsub = None
        try:
            expires_at = await self._refresh_cb()
        except ApiException as err:
            _LOGGER.debug("Failed to refresh stream: %s", err)
            # Increase backoff until the max backoff interval is reached
            self._min_refresh_interval = min(
                self._min_refresh_interval * BACKOFF_MULTIPLIER,
                MAX_REFRESH_BACKOFF_INTERVAL,
            )
            refresh_time = utcnow() + self._min_refresh_interval
        else:
            if expires_at is None:
                return
            self._min_refresh_interval = MIN_REFRESH_BACKOFF_INTERVAL  # Reset backoff
            # Defend against invalid stream expiration time in the past
            refresh_time = max(
                expires_at - STREAM_EXPIRATION_BUFFER,
                utcnow() + self._min_refresh_interval,
            )
        self._schedule_stream_refresh(refresh_time)

    def _schedule_stream_refresh(self, refresh_time: dt.datetime) -> None:
        """Schedules an alarm to refresh any streams before expiration."""
        _LOGGER.debug("Scheduling stream refresh for %s", refresh_time)
        self._unsub = async_track_point_in_utc_time(
            self._hass,
            self._handle_refresh,
            refresh_time,
        )


class NestCameraBaseEntity(Camera, ABC):
    """Devices that support cameras."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_is_streaming = True
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, device: Device) -> None:
        """Initialize the camera."""
        super().__init__()
        self._device = device
        nest_device_info = NestDeviceInfo(device)
        self._attr_device_info = nest_device_info.device_info
        self._attr_brand = nest_device_info.device_brand
        self._attr_model = nest_device_info.device_model
        self.stream_options[CONF_EXTRA_PART_WAIT_TIME] = 3
        # The API "name" field is a unique device identifier.
        # Legacy format, kept as migrating existing unique IDs is not worth the risk
        self._attr_unique_id = f"{self._device.name}-camera"  # pylint: disable=home-assistant-entity-unique-id-redundant-platform

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to register update signal handler."""
        self.async_on_remove(
            self._device.add_update_listener(self.async_write_ha_state)
        )


class NestRTSPEntity(NestCameraBaseEntity):
    """Nest cameras that use RTSP."""

    _rtsp_stream: RtspStream | None = None
    _rtsp_live_stream_trait: CameraLiveStreamTrait

    def __init__(self, device: Device) -> None:
        """Initialize the camera."""
        super().__init__(device)
        self._create_stream_url_lock = asyncio.Lock()
        self._rtsp_live_stream_trait = device.traits[CameraLiveStreamTrait.NAME]
        self._refresh_unsub: Callable[[], None] | None = None

    @property
    @override
    def use_stream_for_stills(self) -> bool:
        """Always use the RTSP stream to generate snapshots."""
        return True

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        # Cameras are marked unavailable on stream errors in #54659 however nest
        # streams have a high error rate (#60353). Given nest streams are so flaky,
        # marking the stream unavailable has other side effects like not showing
        # the camera image which sometimes are still able to work. Until the
        # streams are fixed, just leave the streams as available.
        return True

    @override
    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        async with self._create_stream_url_lock:
            if (rtsp_stream := self._rtsp_stream) is None:
                _LOGGER.debug("Fetching stream url")
                try:
                    rtsp_stream = (
                        await self._rtsp_live_stream_trait.generate_rtsp_stream()
                    )
                except ApiException as err:
                    raise HomeAssistantError(f"Nest API error: {err}") from err
                self._rtsp_stream = rtsp_stream
                refresh = StreamRefresh(
                    self.hass,
                    rtsp_stream.expires_at,
                    self._async_refresh_stream,
                )
                self._refresh_unsub = refresh.unsub
        if rtsp_stream.expires_at < utcnow():
            _LOGGER.warning("Stream already expired")
        return rtsp_stream.rtsp_stream_url

    async def _async_refresh_stream(self) -> dt.datetime | None:
        """Refresh stream to extend expiration time."""
        if not self._rtsp_stream:
            return None
        _LOGGER.debug("Extending RTSP stream")
        try:
            self._rtsp_stream = await self._rtsp_stream.extend_rtsp_stream()
        except ApiException as err:
            _LOGGER.debug("Failed to extend stream: %s", err)
            # Next attempt to catch a url will get a new one
            self._rtsp_stream = None
            if self.stream:
                await self.stream.stop()
                self.stream = None
            return None
        # Update the stream worker with the latest valid url
        if self.stream:
            self.stream.update_source(self._rtsp_stream.rtsp_stream_url)
        return self._rtsp_stream.expires_at

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Invalidates the RTSP token when unloaded."""
        await super().async_will_remove_from_hass()
        if self._refresh_unsub is not None:
            self._refresh_unsub()
        if self._rtsp_stream:
            try:
                await self._rtsp_stream.stop_stream()
            except ApiException as err:
                _LOGGER.debug("Error stopping stream: %s", err)
            self._rtsp_stream = None


class NestWebRTCEntity(NestCameraBaseEntity):
    """Nest cameras that use WebRTC.

    The SDM API has no still image for these cameras, so a placeholder is
    returned. When snapshots over WebRTC are enabled, the camera gives a
    WebRTC provider (go2rtc) a source that opens its own WebRTC session to the
    camera, and fetches still images through it.
    """

    def __init__(
        self, device: Device, snapshot_auth: AsyncConfigEntryAuth | None = None
    ) -> None:
        """Initialize the camera."""
        super().__init__(device)
        self._webrtc_sessions: dict[str, WebRtcStream] = {}
        self._refresh_unsub: dict[str, Callable[[], None]] = {}
        self._snapshot_auth = snapshot_auth
        self._snapshot: bytes | None = None
        self._snapshot_expires_at: dt.datetime | None = None
        self._snapshot_task: asyncio.Task[bytes | None] | None = None
        self._snapshot_retry_interval = SNAPSHOT_MIN_RETRY_INTERVAL
        self._warned_no_provider = False
        # The bundled placeholder is a PNG; the camera platform would otherwise
        # serve it as its default image/jpeg, corrupting the frame for any
        # client that trusts the Content-Type header. Snapshots fetched over
        # WebRTC are JPEG, and the placeholder isn't used then.
        self.content_type = "image/png" if snapshot_auth is None else "image/jpeg"

    @override
    async def async_webrtc_provider_stream_source(self) -> str | None:
        """Return a go2rtc source when snapshots over WebRTC are enabled.

        The source is only for a WebRTC provider. The camera has no
        stream_source, as the stream component can't play it.
        """
        if (auth := self._snapshot_auth) is None:
            return None
        match self._device.name.split("/"):
            case ["enterprises", project_id, "devices", device_id]:
                pass
            case _:
                return None
        query = urlencode(
            {
                "client_id": auth.client_id,
                "client_secret": auth.client_secret,
                "refresh_token": auth.refresh_token,
                "project_id": project_id,
                "device_id": device_id,
                "protocols": StreamingProtocol.WEB_RTC.value,
            }
        )
        return f"nest:?{query}"

    async def _async_refresh_stream(self, session_id: str) -> dt.datetime | None:
        """Refresh stream to extend expiration time."""
        if not (webrtc_stream := self._webrtc_sessions.get(session_id)):
            return None
        _LOGGER.debug("Extending WebRTC stream %s", webrtc_stream.media_session_id)
        try:
            webrtc_stream = await webrtc_stream.extend_stream()
        except FailedPreconditionException as err:
            # The session is no longer valid or the device does not support
            # extending it, retrying only runs into the API rate limit
            _LOGGER.debug(
                "Not refreshing WebRTC stream %s: %s",
                webrtc_stream.media_session_id,
                err,
            )
            return None
        if session_id in self._webrtc_sessions:
            self._webrtc_sessions[session_id] = webrtc_stream
            return webrtc_stream.expires_at
        return None

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image.

        Without snapshots over WebRTC this is a placeholder. Otherwise the
        image is fetched through the WebRTC provider at full size, and the
        camera platform scales it. A failure raises an error, also while the
        next fetch waits, so that a snapshot action doesn't keep an old file.
        """
        if self._snapshot_auth is None:
            return await self.hass.async_add_executor_job(self.placeholder_image)
        if (provider := self.webrtc_provider) is None:
            if not self._warned_no_provider:
                self._warned_no_provider = True
                _LOGGER.warning(
                    "Snapshots over WebRTC for %s need a WebRTC provider that "
                    "supports Nest sources, such as the go2rtc integration",
                    self.entity_id,
                )
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="snapshot_provider_missing"
            )
        if (
            self._snapshot_expires_at is not None
            and utcnow() < self._snapshot_expires_at
        ):
            return self._snapshot_or_raise(self._snapshot)
        if (task := self._snapshot_task) is None or task.done():
            assert self.platform.config_entry
            task = self._snapshot_task = (
                self.platform.config_entry.async_create_background_task(
                    self.hass,
                    self._async_fetch_snapshot(provider),
                    f"{self.entity_id} snapshot",
                )
            )
        # Shielded, so a caller that times out doesn't cancel the fetch that
        # other callers are waiting for and that fills the cache
        try:
            image = await asyncio.shield(task)
        except asyncio.CancelledError:
            # The fetch is cancelled when the config entry is unloaded. Only a
            # caller that is being cancelled itself should see the cancellation.
            caller = cast(asyncio.Task[Any], asyncio.current_task())
            if not task.cancelled() or caller.cancelling():
                raise
            image = None
        return self._snapshot_or_raise(image)

    @staticmethod
    def _snapshot_or_raise(image: bytes | None) -> bytes:
        """Return the snapshot, or raise when there is none."""
        if image is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="snapshot_unavailable"
            )
        return image

    async def _async_fetch_snapshot(
        self, provider: CameraWebRTCProvider
    ) -> bytes | None:
        """Fetch a snapshot through the WebRTC provider and cache it."""
        image: bytes | None = None
        try:
            async with asyncio.timeout(SNAPSHOT_FETCH_TIMEOUT):
                image = await provider.async_get_image(self)
        except (HomeAssistantError, TimeoutError) as err:
            _LOGGER.debug("Unable to get snapshot: %r", err)
        finally:
            # An empty image is a failure too: go2rtc sends an empty response
            # when it can't add a consumer to the stream
            self._snapshot = image or None
            if image:
                self._snapshot_expires_at = utcnow() + SNAPSHOT_CACHE_DURATION
                self._snapshot_retry_interval = SNAPSHOT_MIN_RETRY_INTERVAL
            else:
                self._snapshot_expires_at = utcnow() + self._snapshot_retry_interval
                self._snapshot_retry_interval = min(
                    self._snapshot_retry_interval * 2, SNAPSHOT_MAX_RETRY_INTERVAL
                )
        return image or None

    @classmethod
    @functools.cache
    def placeholder_image(cls) -> bytes:
        """Return placeholder image to use when no stream is available."""
        return PLACEHOLDER.read_bytes()

    @override
    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Return the source of the stream."""
        trait: CameraLiveStreamTrait = self._device.traits[CameraLiveStreamTrait.NAME]
        try:
            stream = await trait.generate_web_rtc_stream(offer_sdp)
        except ApiException as err:
            raise HomeAssistantError(f"Nest API error: {err}") from err
        _LOGGER.debug(
            "Started WebRTC session %s, %s", session_id, stream.media_session_id
        )
        self._webrtc_sessions[session_id] = stream
        send_message(WebRTCAnswer(stream.answer_sdp))
        refresh = StreamRefresh(
            self.hass,
            stream.expires_at,
            functools.partial(self._async_refresh_stream, session_id),
        )
        self._refresh_unsub[session_id] = refresh.unsub

    @override
    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Ignore WebRTC candidates for Nest cloud based cameras."""
        return

    @callback
    @override
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
        if (stream := self._webrtc_sessions.pop(session_id, None)) is not None:
            _LOGGER.debug(
                "Closing WebRTC session %s, %s", session_id, stream.media_session_id
            )
            unsub = self._refresh_unsub.pop(session_id)
            unsub()

            async def stop_stream() -> None:
                try:
                    await stream.stop_stream()
                except ApiException as err:
                    _LOGGER.debug("Error stopping stream: %s", err)

            self.hass.async_create_task(stop_stream())
        super().close_webrtc_session(session_id)

    @callback
    @override
    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return the WebRTC client configuration adjustable per integration."""
        return WebRTCClientConfiguration(data_channel="dataSendChannel")

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Invalidates the RTSP token when unloaded."""
        await super().async_will_remove_from_hass()
        for session_id in list(self._webrtc_sessions.keys()):
            self.close_webrtc_session(session_id)
