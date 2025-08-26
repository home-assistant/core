"""Amcrest data update coordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

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
            }
