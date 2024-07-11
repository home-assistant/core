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
    StreamingProtocol,
)
from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.exceptions import ApiException

from homeassistant.components.camera import Camera, CameraEntityFeature, StreamType
from homeassistant.components.stream import CONF_EXTRA_PART_WAIT_TIME
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
        self._stream: RtspStream | None = None
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
            if not self._stream:
                _LOGGER.debug("Fetching stream url")
                try:
                    self._stream = (
                        await self._rtsp_live_stream_trait.generate_rtsp_stream()
                    )
                except ApiException as err:
                    raise HomeAssistantError(f"Nest API error: {err}") from err
                self._schedule_stream_refresh()
        assert self._stream
        if self._stream.expires_at < utcnow():
            _LOGGER.warning("Stream already expired")
        return self._stream.rtsp_stream_url

    def _schedule_stream_refresh(self) -> None:
        """Schedules an alarm to refresh the stream url before expiration."""
        assert self._stream
        _LOGGER.debug("New stream url expires at %s", self._stream.expires_at)
        refresh_time = self._stream.expires_at - STREAM_EXPIRATION_BUFFER
        # Schedule an alarm to extend the stream
        if self._stream_refresh_unsub is not None:
            self._stream_refresh_unsub()

        self._stream_refresh_unsub = async_track_point_in_utc_time(
            self.hass,
            self._handle_stream_refresh,
            refresh_time,
        )

    async def _handle_stream_refresh(self, now: datetime.datetime) -> None:
        """Alarm that fires to check if the stream should be refreshed."""
        if not self._stream:
            return
        _LOGGER.debug("Extending stream url")
        try:
            self._stream = await self._stream.extend_rtsp_stream()
        except ApiException as err:
            _LOGGER.debug("Failed to extend stream: %s", err)
            # Next attempt to catch a url will get a new one
            self._stream = None
            if self.stream:
                await self.stream.stop()
                self.stream = None
            return
        # Update the stream worker with the latest valid url
        if self.stream:
            self.stream.update_source(self._stream.rtsp_stream_url)
        self._schedule_stream_refresh()

    async def async_will_remove_from_hass(self) -> None:
        """Invalidates the RTSP token when unloaded."""
        if self._stream:
            _LOGGER.debug("Invalidating stream")
            try:
                await self._stream.stop_rtsp_stream()
            except ApiException as err:
                _LOGGER.debug(
                    "Failed to revoke stream token, will rely on ttl: %s", err
                )
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

    async def async_handle_web_rtc_offer(self, offer_sdp: str) -> str | None:
        """Return the source of the stream."""
        trait: CameraLiveStreamTrait = self._device.traits[CameraLiveStreamTrait.NAME]
        if StreamingProtocol.WEB_RTC not in trait.supported_protocols:
            return await super().async_handle_web_rtc_offer(offer_sdp)
        try:
            stream = await trait.generate_web_rtc_stream(offer_sdp)
        except ApiException as err:
            raise HomeAssistantError(f"Nest API error: {err}") from err
        return stream.answer_sdp
