"""Support for Hikvision cameras."""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client

from . import HikvisionConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Timeout for fetching camera snapshot
SNAPSHOT_TIMEOUT = 10

# Default RTSP port for Hikvision devices
DEFAULT_RTSP_PORT = 554


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hikvision cameras from a config entry."""
    data = entry.runtime_data
    camera = data.camera

    entities: list[HikvisionCamera] = []

    # Get channels from current event states (same approach as binary sensors)
    sensors = camera.current_event_states
    if sensors:
        # Collect unique channels from all event types
        channels: set[int] = set()
        for channel_list in sensors.values():
            for channel_info in channel_list:
                channels.add(channel_info[1])

        # Create a camera entity for each channel
        entities.extend(HikvisionCamera(entry, channel) for channel in sorted(channels))
    else:
        # Single camera device (no NVR channels detected)
        entities.append(HikvisionCamera(entry, 1))

    async_add_entities(entities)


class HikvisionCamera(Camera):
    """Representation of a Hikvision camera."""

    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        entry: HikvisionConfigEntry,
        channel: int,
    ) -> None:
        """Initialize the camera."""
        super().__init__()
        self._entry = entry
        self._data = entry.runtime_data
        self._channel = channel

        # Connection parameters
        self._host = entry.data[CONF_HOST]
        self._port = entry.data[CONF_PORT]
        self._username = entry.data[CONF_USERNAME]
        self._password = entry.data[CONF_PASSWORD]
        self._ssl = entry.data[CONF_SSL]
        self._protocol = "https" if self._ssl else "http"

        # Build unique ID
        self._attr_unique_id = f"{self._data.device_id}_camera_{channel}"

        # Build entity name based on device type
        if self._data.device_type == "NVR":
            self._attr_name = f"Channel {channel}"
        else:
            self._attr_name = None  # Use device name

        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._data.device_id)},
            name=self._data.device_name,
            manufacturer="Hikvision",
            model=self._data.device_type,
        )

    def _get_snapshot_url(self) -> str:
        """Get the snapshot URL for the channel."""
        # Hikvision ISAPI snapshot URL format
        # For NVRs: channel 1 = 101, channel 2 = 201, etc.
        # For cameras: channel 1 = 1
        if self._data.device_type == "NVR":
            stream_channel = self._channel * 100 + 1  # Main stream
        else:
            stream_channel = 1

        return (
            f"{self._protocol}://{self._host}:{self._port}"
            f"/ISAPI/Streaming/channels/{stream_channel}/picture"
        )

    def _get_rtsp_url(self) -> str:
        """Get the RTSP stream URL for the channel."""
        # Hikvision RTSP URL format
        # For NVRs: channel 1 main = 101, channel 1 sub = 102
        # For cameras: main = 1, sub = 2
        if self._data.device_type == "NVR":
            stream_channel = self._channel * 100 + 1  # Main stream
        else:
            stream_channel = 1

        # URL-encode credentials for safety
        username = quote(self._username, safe="")
        password = quote(self._password, safe="")

        return (
            f"rtsp://{username}:{password}"
            f"@{self._host}:{DEFAULT_RTSP_PORT}/Streaming/Channels/{stream_channel}"
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the camera."""
        url = self._get_snapshot_url()

        try:
            async_client = get_async_client(self.hass, verify_ssl=self._ssl)
            response = await async_client.get(
                url,
                auth=httpx.DigestAuth(self._username, self._password),
                timeout=SNAPSHOT_TIMEOUT,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            _LOGGER.error(
                "Timeout getting camera image from %s channel %d",
                self._data.device_name,
                self._channel,
            )
            return None
        except httpx.HTTPStatusError as err:
            _LOGGER.error(
                "HTTP error getting camera image from %s channel %d: %s",
                self._data.device_name,
                self._channel,
                err,
            )
            return None
        except httpx.RequestError as err:
            _LOGGER.error(
                "Error getting camera image from %s channel %d: %s",
                self._data.device_name,
                self._channel,
                err,
            )
            return None

        return response.content

    async def stream_source(self) -> str | None:
        """Return the stream source URL."""
        return self._get_rtsp_url()
