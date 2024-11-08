"""Support for Google Nest SDM Cameras."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Callable
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

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    StreamType,
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
        self._stream_refresh_unsub: Callable[[], None] | None = None

    @abstractmethod
    def _stream_expires_at(self) -> datetime.datetime | None:
        """Next time when a stream expires."""

    @abstractmethod
    async def _async_refresh_stream(self) -> None:
        """Refresh any stream to extend expiration time."""

    def _schedule_stream_refresh(self) -> None:
        """Schedules an alarm to refresh any streams before expiration."""
        if self._stream_refresh_unsub is not None:
            self._stream_refresh_unsub()

        expiration_time = self._stream_expires_at()
        if not expiration_time:
            return
        refresh_time = expiration_time - STREAM_EXPIRATION_BUFFER
        _LOGGER.debug("Scheduled next stream refresh for %s", refresh_time)

        self._stream_refresh_unsub = async_track_point_in_utc_time(
            self.hass,
            self._handle_stream_refresh,
            refresh_time,
        )

    async def _handle_stream_refresh(self, _: datetime.datetime) -> None:
        """Alarm that fires to check if the stream should be refreshed."""
        _LOGGER.debug("Examining streams to refresh")
        self._stream_refresh_unsub = None
        try:
            await self._async_refresh_stream()
        finally:
            self._schedule_stream_refresh()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to register update signal handler."""
        self.async_on_remove(
            self._device.add_update_listener(self.async_write_ha_state)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Invalidates the RTSP token when unloaded."""
        await super().async_will_remove_from_hass()
        if self._stream_refresh_unsub:
            self._stream_refresh_unsub()


class NestRTSPEntity(NestCameraBaseEntity):
    """Nest cameras that use RTSP."""

    _rtsp_stream: RtspStream | None = None
    _rtsp_live_stream_trait: CameraLiveStreamTrait

    def __init__(self, device: Device) -> None:
        """Initialize the camera."""
        super().__init__(device)
        self._create_stream_url_lock = asyncio.Lock()
        self._rtsp_live_stream_trait = device.traits[CameraLiveStreamTrait.NAME]

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
                self._schedule_stream_refresh()
        assert self._rtsp_stream
        if self._rtsp_stream.expires_at < utcnow():
            _LOGGER.warning("Stream already expired")
        return self._rtsp_stream.rtsp_stream_url

    def _stream_expires_at(self) -> datetime.datetime | None:
        """Next time when a stream expires."""
        return self._rtsp_stream.expires_at if self._rtsp_stream else None

    async def _async_refresh_stream(self) -> None:
        """Refresh stream to extend expiration time."""
        if not self._rtsp_stream:
            return
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
            return
        # Update the stream worker with the latest valid url
        if self.stream:
            self.stream.update_source(self._rtsp_stream.rtsp_stream_url)

    async def async_will_remove_from_hass(self) -> None:
        """Invalidates the RTSP token when unloaded."""
        await super().async_will_remove_from_hass()
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

    @property
    def frontend_stream_type(self) -> StreamType | None:
        """Return the type of stream supported by this camera."""
        return StreamType.WEB_RTC

    def _stream_expires_at(self) -> datetime.datetime | None:
        """Next time when a stream expires."""
        if not self._webrtc_sessions:
            return None
        return min(stream.expires_at for stream in self._webrtc_sessions.values())

    async def _async_refresh_stream(self) -> None:
        """Refresh stream to extend expiration time."""
        now = utcnow()
        for webrtc_stream in list(self._webrtc_sessions.values()):
            if now < (webrtc_stream.expires_at - STREAM_EXPIRATION_BUFFER):
                _LOGGER.debug(
                    "Stream does not yet expire: %s", webrtc_stream.expires_at
                )
                continue
            _LOGGER.debug("Extending WebRTC stream %s", webrtc_stream.media_session_id)
            try:
                webrtc_stream = await webrtc_stream.extend_stream()
            except ApiException as err:
                _LOGGER.debug("Failed to extend stream: %s", err)
            else:
                self._webrtc_sessions[webrtc_stream.media_session_id] = webrtc_stream

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
        self._schedule_stream_refresh()

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
        if (stream := self._webrtc_sessions.pop(session_id, None)) is not None:
            _LOGGER.debug(
                "Closing WebRTC session %s, %s", session_id, stream.media_session_id
            )

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
