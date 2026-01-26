"""Amcrest data update coordinator."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from amcrest import AmcrestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import AmcrestChecker
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

    def _get_enabled_entity_keys(self) -> set[str]:
        """Get entity description keys for all enabled entities in this config entry."""
        entity_registry = er.async_get(self.hass)
        enabled_keys: set[str] = set()

        if self.config_entry is None:
            _LOGGER.debug("No entities are enabled to update")
            return enabled_keys

        # Get all entities for this config entry
        entities = er.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        for entity in entities:
            if not entity.disabled:
                # Extract the key from the entity's unique_id or entity_id
                # For Amcrest entities, the unique_id typically ends with the key
                # e.g., "ABC123_storage" -> "storage", "ABC123_ptz_presets" -> "ptz_presets"
                if entity.unique_id and "_" in entity.unique_id:
                    key = entity.unique_id.split("_", 1)[
                        1
                    ]  # Get everything after first underscore
                    enabled_keys.add(key)

        _LOGGER.debug(
            "Found enabled entity keys for %s: %s", self.device.name, enabled_keys
        )
        return enabled_keys

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Get enabled entity keys first
            enabled_keys = self._get_enabled_entity_keys()
            _LOGGER.debug("Processing %d enabled entities", len(enabled_keys))

            # Update device data first
            await self.device.async_get_data()

            # Get camera data similar to AmcrestCam.async_update
            api = self.device.api

            # Get brand, model, serial, and RTSP URL (these are properties)
            brand = await api.async_vendor_information
            model = await api.async_device_type
            serial = await api.async_serial_number
            rtsp_url = await api.async_rtsp_url(typeno=self.device.resolution)

            channel = self.device.channel
            # Get camera states using helper methods that would be in camera.py
            # For now, let's use the basic API calls with proper parameters

            required_entity_data_function_map: dict[
                str, Callable[[], Awaitable[Any]] | Awaitable[Any]
            ] = {
                "is_streaming": lambda: api.async_is_video_enabled(
                    channel=channel, stream="Main"
                ),
                "is_recording": api.async_record_mode,
                "motion_detection_enabled": lambda: api.async_is_motion_detector_on(),  # pylint: disable=unnecessary-lambda
                "color_bw": api.async_day_night_color,
            }

            # Define entity data mapping
            optional_entity_data_function_map: dict[
                str, Callable[[], Awaitable[Any]] | Awaitable[Any]
            ] = {
                "online": lambda: api.async_current_time,  # pylint: disable=unnecessary-lambda
                "audio_detected_polled": lambda: self._check_audio_events(api),
                "audio_enabled": lambda: api.async_is_audio_enabled(
                    channel=channel, stream="Main"
                ),
                "motion_detected_polled": lambda: api.async_event_channels_happened(
                    "VideoMotion"
                ),
                "motion_recording_enabled": lambda: api.async_is_record_on_motion_detection(),  # pylint: disable=unnecessary-lambda
                "crossline_detected_polled": lambda: api.async_event_channels_happened(
                    "CrossLineDetection"
                ),
                "ptz_preset": lambda: api.async_ptz_presets_count,  # pylint: disable=unnecessary-lambda
                "sdcard": lambda: api.async_storage_all,  # pylint: disable=unnecessary-lambda
                "privacy_mode": lambda: api.async_privacy_config(),  # pylint: disable=unnecessary-lambda
            }

            # Initialize all entity data results to None
            data_results = dict.fromkeys(required_entity_data_function_map, None)
            data_results.update(dict.fromkeys(optional_entity_data_function_map, None))

            task_functions: list[Callable[[], Awaitable[Any]] | Awaitable[Any]] = []
            enabled_detection_keys: list[str] = []

            # add required data to tasks
            for key, func in required_entity_data_function_map.items():
                task_functions.append(func)  # Store function, don't call yet
                enabled_detection_keys.append(key)

            # check enabled entities and add to tasks if enabled
            for key, func in optional_entity_data_function_map.items():
                if key in enabled_keys:
                    task_functions.append(func)  # Store function, don't call yet
                    enabled_detection_keys.append(key)

            # Execute enabled entity data fetches concurrently
            if task_functions:
                # Create coroutines just before passing to gather to avoid unawaited coroutines
                tasks = []
                for func_or_coro in task_functions:
                    if callable(func_or_coro):
                        tasks.append(func_or_coro())
                    else:
                        tasks.append(func_or_coro)
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for i, key in enumerate(enabled_detection_keys):
                    if isinstance(results[i], Exception):
                        _LOGGER.warning("Unable to fetch '%s': %s", key, results[i])
                        data_results[key] = None
                    else:
                        _LOGGER.debug("Fetched '%s': %s", key, results[i])
                        data_results[key] = results[i]

            # Extract individual variables for backwards compatibility
            online = not isinstance(data_results["online"], AmcrestError)
            is_streaming = data_results["is_streaming"]
            is_recording = data_results["is_recording"]
            motion_detection_enabled = data_results["motion_detection_enabled"]
            audio_enabled = data_results["audio_enabled"]
            color_bw = data_results["color_bw"]
            audio_detected = data_results["audio_detected_polled"]
            motion_detected = data_results["motion_detected_polled"]
            motion_recording_enabled = data_results["motion_recording_enabled"]
            crossline_detected = data_results["crossline_detected_polled"]
            ptz_presets_count = data_results["ptz_preset"]
            storage_info = data_results["sdcard"]
            privacy_mode = (
                None
                if data_results["privacy_mode"] is None
                else data_results["privacy_mode"].splitlines()[0].split("=")[1]
                == "true"
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
                "motion_recording_enabled": motion_recording_enabled,
                "privacy_mode": privacy_mode,
            }

    async def _check_audio_events(self, api: AmcrestChecker) -> bool:
        """Check for audio events (AudioMutation or AudioIntensity)."""
        try:
            for event_code in ("AudioMutation", "AudioIntensity"):
                if await api.async_event_channels_happened(event_code):
                    return True
        except AmcrestError:
            return False
        else:
            return False
