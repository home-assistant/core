"""Support for Google Nest SDM Cameras."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import datetime
import functools
import logging
from pathlib import Path
from typing import cast

from google_nest_sdm.camera_traits import (
    CameraImageTrait,
    CameraLiveStreamTrait,
    RtspStream,
    Stream,
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
    async_add_entities(
        NestCamera(device)
        for device in device_manager.devices.values()
        if CameraImageTrait.NAME in device.traits
        or CameraLiveStreamTrait.NAME in device.traits
    )


class NestCamera(Camera):
    """Devices that support cameras."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device: Device) -> None:
        """Initialize the camera."""
        super().__init__()
        self._device = device
        nest_device_info = NestDeviceInfo(device)
        self._attr_device_info = nest_device_info.device_info
        self._attr_brand = nest_device_info.device_brand
        self._attr_model = nest_device_info.device_model
        self._rtsp_stream: RtspStream | None = None
        self._webrtc_sessions: dict[str, WebRtcStream] = {}
        self._create_stream_url_lock = asyncio.Lock()
        self._stream_refresh_unsub: Callable[[], None] | None = None
        self._attr_is_streaming = False
        self._attr_supported_features = CameraEntityFeature(0)
        self._rtsp_live_stream_trait: CameraLiveStreamTrait | None = None
        if CameraLiveStreamTrait.NAME in self._device.traits:
            self._attr_is_streaming = True
            self._attr_supported_features |= CameraEntityFeature.STREAM
            trait = cast(
                CameraLiveStreamTrait, self._device.traits[CameraLiveStreamTrait.NAME]
            )
            if StreamingProtocol.RTSP in trait.supported_protocols:
                self._rtsp_live_stream_trait = trait
        self.stream_options[CONF_EXTRA_PART_WAIT_TIME] = 3
        # The API "name" field is a unique device identifier.
        self._attr_unique_id = f"{self._device.name}-camera"

    @property
    def use_stream_for_stills(self) -> bool:
        """Whether or not to use stream to generate stills."""
        return self._rtsp_live_stream_trait is not None

    @property
    def frontend_stream_type(self) -> StreamType | None:
        """Return the type of stream supported by this camera."""
        if CameraLiveStreamTrait.NAME not in self._device.traits:
            return None
        trait = self._device.traits[CameraLiveStreamTrait.NAME]
        if StreamingProtocol.WEB_RTC in trait.supported_protocols:
            return StreamType.WEB_RTC
        return super().frontend_stream_type

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
        if not self._rtsp_live_stream_trait:
            return None
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

    def _all_streams(self) -> list[Stream]:
        """Return the current list of active streams."""
        streams: list[Stream] = []
        if self._rtsp_stream:
            streams.append(self._rtsp_stream)
        streams.extend(list(self._webrtc_sessions.values()))
        return streams

    def _schedule_stream_refresh(self) -> None:
        """Schedules an alarm to refresh any streams before expiration."""
        # Schedule an alarm to extend the stream
        if self._stream_refresh_unsub is not None:
            self._stream_refresh_unsub()

        _LOGGER.debug("Scheduling next stream refresh")
        expiration_times = [stream.expires_at for stream in self._all_streams()]
        if not expiration_times:
            _LOGGER.debug("No streams to refresh")
            return

        refresh_time = min(expiration_times) - STREAM_EXPIRATION_BUFFER
        _LOGGER.debug("Scheduled next stream refresh for %s", refresh_time)

        self._stream_refresh_unsub = async_track_point_in_utc_time(
            self.hass,
            self._handle_stream_refresh,
            refresh_time,
        )

    async def _handle_stream_refresh(self, _: datetime.datetime) -> None:
        """Alarm that fires to check if the stream should be refreshed."""
        _LOGGER.debug("Examining streams to refresh")
        await self._handle_rtsp_stream_refresh()
        await self._handle_webrtc_stream_refresh()
        self._schedule_stream_refresh()

    async def _handle_rtsp_stream_refresh(self) -> None:
        """Alarm that fires to check if the stream should be refreshed."""
        if not self._rtsp_stream:
            return
        now = utcnow()
        refresh_time = self._rtsp_stream.expires_at - STREAM_EXPIRATION_BUFFER
        if now < refresh_time:
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

    async def _handle_webrtc_stream_refresh(self) -> None:
        """Alarm that fires to check if the stream should be refreshed."""
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

    async def async_will_remove_from_hass(self) -> None:
        """Invalidates the RTSP token when unloaded."""
        for stream in self._all_streams():
            _LOGGER.debug("Invalidating stream")
            try:
                await stream.stop_stream()
            except ApiException as err:
                _LOGGER.debug("Error stopping stream: %s", err)
        self._rtsp_stream = None
        self._webrtc_sessions.clear()

        if self._stream_refresh_unsub:
            self._stream_refresh_unsub()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to register update signal handler."""
        self.async_on_remove(
            self._device.add_update_listener(self.async_write_ha_state)
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        # Use the thumbnail from RTSP stream, or a placeholder if stream is
        # not supported (e.g. WebRTC) as a fallback when 'use_stream_for_stills' if False
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
        if StreamingProtocol.WEB_RTC not in trait.supported_protocols:
            await super().async_handle_async_webrtc_offer(
                offer_sdp, session_id, send_message
            )
            return
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
