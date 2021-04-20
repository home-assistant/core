"""Support for Google Nest SDM Cameras."""
from __future__ import annotations

import datetime
import logging

from google_nest_sdm.camera_traits import (
    CameraEventImageTrait,
    CameraImageTrait,
    CameraLiveStreamTrait,
)
from google_nest_sdm.device import Device
from google_nest_sdm.exceptions import GoogleNestException
from haffmpeg.tools import IMAGE_JPEG

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.components.ffmpeg import async_get_image
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.dt import utcnow

from .const import DATA_SUBSCRIBER, DOMAIN
from .device_info import DeviceInfo

_LOGGER = logging.getLogger(__name__)

# Used to schedule an alarm to refresh the stream before expiration
STREAM_EXPIRATION_BUFFER = datetime.timedelta(seconds=30)


async def async_setup_sdm_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the cameras."""

    subscriber = hass.data[DOMAIN][DATA_SUBSCRIBER]
    try:
        device_manager = await subscriber.async_get_device_manager()
    except GoogleNestException as err:
        raise PlatformNotReady from err

    # Fetch initial data so we have data when entities subscribe.

    entities = []
    for device in device_manager.devices.values():
        if (
            CameraImageTrait.NAME in device.traits
            or CameraLiveStreamTrait.NAME in device.traits
        ):
            entities.append(NestCamera(device))
    async_add_entities(entities)


class NestCamera(Camera):
    """Devices that support cameras."""

    def __init__(self, device: Device):
        """Initialize the camera."""
        super().__init__()
        self._device = device
        self._device_info = DeviceInfo(device)
        self._stream = None
        self._stream_refresh_unsub = None
        # Cache of most recent event image
        self._event_id = None
        self._event_image_bytes = None
        self._event_image_cleanup_unsub = None

    @property
    def should_poll(self) -> bool:
        """Disable polling since entities have state pushed via pubsub."""
        return False

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        # The API "name" field is a unique device identifier.
        return f"{self._device.name}-camera"

    @property
    def name(self):
        """Return the name of the camera."""
        return self._device_info.device_name

    @property
    def device_info(self):
        """Return device specific attributes."""
        return self._device_info.device_info

    @property
    def brand(self):
        """Return the camera brand."""
        return self._device_info.device_brand

    @property
    def model(self):
        """Return the camera model."""
        return self._device_info.device_model

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0
        if CameraLiveStreamTrait.NAME in self._device.traits:
            supported_features |= SUPPORT_STREAM
        return supported_features

    async def stream_source(self):
        """Return the source of the stream."""
        if CameraLiveStreamTrait.NAME not in self._device.traits:
            return None
        trait = self._device.traits[CameraLiveStreamTrait.NAME]
        if not self._stream:
            _LOGGER.debug("Fetching stream url")
            self._stream = await trait.generate_rtsp_stream()
            self._schedule_stream_refresh()
        if self._stream.expires_at < utcnow():
            _LOGGER.warning("Stream already expired")
        return self._stream.rtsp_stream_url

    def _schedule_stream_refresh(self):
        """Schedules an alarm to refresh the stream url before expiration."""
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

    async def _handle_stream_refresh(self, now):
        """Alarm that fires to check if the stream should be refreshed."""
        if not self._stream:
            return
        _LOGGER.debug("Extending stream url")
        try:
            self._stream = await self._stream.extend_rtsp_stream()
        except GoogleNestException as err:
            _LOGGER.debug("Failed to extend stream: %s", err)
            # Next attempt to catch a url will get a new one
            self._stream = None
            if self.stream:
                self.stream.stop()
                self.stream = None
            return
        # Update the stream worker with the latest valid url
        if self.stream:
            self.stream.update_source(self._stream.rtsp_stream_url)
        self._schedule_stream_refresh()

    async def async_will_remove_from_hass(self):
        """Invalidates the RTSP token when unloaded."""
        if self._stream:
            _LOGGER.debug("Invalidating stream")
            await self._stream.stop_rtsp_stream()
        if self._stream_refresh_unsub:
            self._stream_refresh_unsub()
        self._event_id = None
        self._event_image_bytes = None
        if self._event_image_cleanup_unsub is not None:
            self._event_image_cleanup_unsub()

    async def async_added_to_hass(self):
        """Run when entity is added to register update signal handler."""
        self.async_on_remove(
            self._device.add_update_listener(self.async_write_ha_state)
        )

    async def async_camera_image(self):
        """Return bytes of camera image."""
        # Returns the snapshot of the last event for ~30 seconds after the event
        active_event_image = await self._async_active_event_image()
        if active_event_image:
            return active_event_image
        # Fetch still image from the live stream
        stream_url = await self.stream_source()
        if not stream_url:
            return None
        return await async_get_image(self.hass, stream_url, output_format=IMAGE_JPEG)

    async def _async_active_event_image(self):
        """Return image from any active events happening."""
        if CameraEventImageTrait.NAME not in self._device.traits:
            return None
        trait = self._device.active_event_trait
        if not trait:
            return None
        # Reuse image bytes if they have already been fetched
        event = trait.last_event
        if self._event_id is not None and self._event_id == event.event_id:
            return self._event_image_bytes
        _LOGGER.debug("Generating event image URL for event_id %s", event.event_id)
        image_bytes = await self._async_fetch_active_event_image(trait)
        if image_bytes is None:
            return None
        self._event_id = event.event_id
        self._event_image_bytes = image_bytes
        self._schedule_event_image_cleanup(event.expires_at)
        return image_bytes

    async def _async_fetch_active_event_image(self, trait):
        """Return image bytes for an active event."""
        try:
            event_image = await trait.generate_active_event_image()
        except GoogleNestException as err:
            _LOGGER.debug("Unable to generate event image URL: %s", err)
            return None
        if not event_image:
            return None
        try:
            return await event_image.contents()
        except GoogleNestException as err:
            _LOGGER.debug("Unable to fetch event image: %s", err)
            return None

    def _schedule_event_image_cleanup(self, point_in_time):
        """Schedules an alarm to remove the image bytes from memory, honoring expiration."""
        if self._event_image_cleanup_unsub is not None:
            self._event_image_cleanup_unsub()
        self._event_image_cleanup_unsub = async_track_point_in_utc_time(
            self.hass,
            self._handle_event_image_cleanup,
            point_in_time,
        )

    def _handle_event_image_cleanup(self, now):
        """Clear images cached from events and scheduled callback."""
        self._event_id = None
        self._event_image_bytes = None
        self._event_image_cleanup_unsub = None
