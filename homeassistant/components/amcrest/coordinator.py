"""Amcrest data update coordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from amcrest import AmcrestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from .models import AmcrestConfiguredDevice

_LOGGER = logging.getLogger(__name__)


class AmcrestDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Define an object to manage fetching Amcrest data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: AmcrestConfiguredDevice,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Amcrest",
            config_entry=config_entry,
            update_interval=update_interval,
        )
        self.device = device

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Update device data first
            await self.device.async_get_data()

            # Get camera data similar to AmcrestCam.async_update
            api = self.device.api

            # Get brand, model, serial, and RTSP URL (these are properties)
            brand = await api.async_vendor_information
            model = await api.async_device_type
            serial = await api.async_serial_number
            rtsp_url = await api.async_rtsp_url(typeno=self.device.resolution)

            # Get camera states using helper methods that would be in camera.py
            # For now, let's use the basic API calls with proper parameters
            (
                is_streaming,
                is_recording,
                motion_detection_enabled,
                audio_enabled,
                motion_recording_enabled,
                color_bw,
            ) = await asyncio.gather(
                api.async_is_video_enabled(channel=self.device.channel),
                api.async_record_mode,
                api.async_is_motion_detector_on(channel=self.device.channel),
                api.async_is_audio_enabled(channel=self.device.channel),
                api.async_is_record_on_motion_detection(channel=self.device.channel),
                api.async_day_night_color,
            )

            # Get binary sensor data - online status and event detection
            # Online status: test connectivity with current_time
            try:
                await api.async_current_time
                online = True
            except AmcrestError:
                online = False

            # Get event detection states for binary sensors
            (
                audio_detected,
                motion_detected,
                crossline_detected,
            ) = await asyncio.gather(
                # Check for audio events (AudioMutation or AudioIntensity)
                self._check_audio_events(api),
                # Check for motion event (VideoMotion)
                api.async_event_channels_happened("VideoMotion"),
                # Check for crossline event (CrossLineDetection)
                api.async_event_channels_happened("CrossLineDetection"),
                return_exceptions=True,
            )

            # Handle exceptions from event checks
            if isinstance(audio_detected, Exception):
                audio_detected = False
            if isinstance(motion_detected, Exception):
                motion_detected = False
            if isinstance(crossline_detected, Exception):
                crossline_detected = False

            # Get sensor data - PTZ presets and storage
            (
                ptz_presets_count,
                storage_info,
            ) = await asyncio.gather(
                api.async_ptz_presets_count,
                api.async_storage_all,
                return_exceptions=True,
            )

            # Handle exceptions from sensor data
            if isinstance(ptz_presets_count, Exception):
                ptz_presets_count = None
            if isinstance(storage_info, Exception):
                storage_info = None

            # Get switch data - privacy mode
            try:
                privacy_config = await api.async_privacy_config()
                privacy_mode = privacy_config.splitlines()[0].split("=")[1] == "true"
            except AmcrestError:
                privacy_mode = None

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return {
                "serial_number": self.device.serial_number,
                "device_name": self.device.name,
                # Camera data
                "brand": brand,
                "model": model,
                "serial": serial,
                "rtsp_url": rtsp_url,
                "is_streaming": is_streaming,
                "is_recording": is_recording,
                "motion_detection_enabled": motion_detection_enabled,
                "audio_enabled": audio_enabled,
                "motion_recording_enabled": motion_recording_enabled,
                "color_bw": color_bw,
                # Binary sensor data
                "online": online,
                "audio_detected": audio_detected,
                "motion_detected": motion_detected,
                "crossline_detected": crossline_detected,
                # Sensor data
                "ptz_presets_count": ptz_presets_count,
                "storage_info": storage_info,
                # Switch data
                "privacy_mode": privacy_mode,
            }

    async def _check_audio_events(self, api) -> bool:
        """Check for audio events (AudioMutation or AudioIntensity)."""
        try:
            for event_code in ["AudioMutation", "AudioIntensity"]:
                if await api.async_event_channels_happened(event_code):
                    return True
        except AmcrestError:
            return False
        else:
            return False
