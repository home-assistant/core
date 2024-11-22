"""Support for Google Nest SDM Cameras."""

from __future__ import annotations

from abc import ABC
import asyncio
from collections.abc import Awaitable, Callable
import datetime
import functools
import logging
from pathlib import Path

from google_nest_sdm.camera_traits import (
    CameraLiveStreamTrait,
    RtspStream,
    StreamingProtocol,
    WebRtcStream,
)
from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.exceptions import ApiException
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    WebRTCAnswer,
    WebRTCClientConfiguration,
    WebRTCSendMessage,
)
from homeassistant.components.stream import CONF_EXTRA_PART_WAIT_TIME
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from .const import DATA_DEVICE_MANAGER, DOMAIN
from .device_info import NestDeviceInfo

_LOGGER = logging.getLogger(__name__)

PLACEHOLDER = Path(__file__).parent / "placeholder.png"

# Used to schedule an alarm to refresh the stream before expiration
STREAM_EXPIRATION_BUFFER = datetime.timedelta(seconds=30)

# Refresh streams with a bounded interval and backoff on failure
MIN_REFRESH_BACKOFF_INTERVAL = datetime.timedelta(minutes=1)
MAX_REFRESH_BACKOFF_INTERVAL = datetime.timedelta(minutes=10)
BACKOFF_MULTIPLIER = 1.5


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the cameras."""

    device_manager: DeviceManager = hass.data[DOMAIN][entry.entry_id][
        DATA_DEVICE_MANAGER
    ]
    entities: list[NestCameraBaseEntity] = []
    for device in device_manager.devices.values():
        if (live_stream := device.traits.get(CameraLiveStreamTrait.NAME)) is None:
            continue
        if StreamingProtocol.WEB_RTC in live_stream.supported_protocols:
            entities.append(NestWebRTCEntity(device))
        elif StreamingProtocol.RTSP in live_stream.supported_protocols:
            entities.append(NestRTSPEntity(device))

    async_add_entities(entities)


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
        expires_at: datetime.datetime,
        refresh_cb: Callable[[], Awaitable[datetime.datetime | None]],
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

    async def _handle_refresh(self, _: datetime.datetime) -> None:
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

    def _schedule_stream_refresh(self, refresh_time: datetime.datetime) -> None:
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
        self._attr_unique_id = f"{self._device.name}-camera"

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
    def use_stream_for_stills(self) -> bool:
        """Always use the RTSP stream to generate snapshots."""
        return True

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Cameras are marked unavailable on stream errors in #54659 however nest
        # streams have a high error rate (#60353). Given nest streams are so flaky,
        # marking the stream unavailable has other side effects like not showing
        # the camera image which sometimes are still able to work. Until the
        # streams are fixed, just leave the streams as available.
        return True

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        async with self._create_stream_url_lock:
            if not self._rtsp_stream:
                _LOGGER.debug("Fetching stream url")
                try:
                    self._rtsp_stream = (
                        await self._rtsp_live_stream_trait.generate_rtsp_stream()
                    )
                except ApiException as err:
                    raise HomeAssistantError(f"Nest API error: {err}") from err
                refresh = StreamRefresh(
                    self.hass,
                    self._rtsp_stream.expires_at,
                    self._async_refresh_stream,
                )
                self._refresh_unsub = refresh.unsub
        assert self._rtsp_stream
        if self._rtsp_stream.expires_at < utcnow():
            _LOGGER.warning("Stream already expired")
        return self._rtsp_stream.rtsp_stream_url

    async def _async_refresh_stream(self) -> datetime.datetime | None:
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
    """Nest cameras that use WebRTC."""

    def __init__(self, device: Device) -> None:
        """Initialize the camera."""
        super().__init__(device)
        self._webrtc_sessions: dict[str, WebRtcStream] = {}
        self._refresh_unsub: dict[str, Callable[[], None]] = {}

    async def _async_refresh_stream(self, session_id: str) -> datetime.datetime | None:
        """Refresh stream to extend expiration time."""
        if not (webrtc_stream := self._webrtc_sessions.get(session_id)):
            return None
        _LOGGER.debug("Extending WebRTC stream %s", webrtc_stream.media_session_id)
        webrtc_stream = await webrtc_stream.extend_stream()
        if session_id in self._webrtc_sessions:
            self._webrtc_sessions[session_id] = webrtc_stream
            return webrtc_stream.expires_at
        return None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a placeholder image for WebRTC cameras that don't support snapshots."""
        return await self.hass.async_add_executor_job(self.placeholder_image)

    @classmethod
    @functools.cache
    def placeholder_image(cls) -> bytes:
        """Return placeholder image to use when no stream is available."""
        return PLACEHOLDER.read_bytes()

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

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Ignore WebRTC candidates for Nest cloud based cameras."""
        return

    @callback
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
    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return the WebRTC client configuration adjustable per integration."""
        return WebRTCClientConfiguration(data_channel="dataSendChannel")

    async def async_will_remove_from_hass(self) -> None:
        """Invalidates the RTSP token when unloaded."""
        await super().async_will_remove_from_hass()
        for session_id in list(self._webrtc_sessions.keys()):
            self.close_webrtc_session(session_id)
