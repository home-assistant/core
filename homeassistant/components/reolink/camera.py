"""This component provides support for Reolink IP cameras."""
from __future__ import annotations

import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ReolinkCoordinatorEntity
from .host import ReolinkHost

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up a Reolink IP Camera."""
    host: ReolinkHost = hass.data[DOMAIN][config_entry.entry_id].host

    cameras = []
    for channel in host.api.channels:
        streams = ["sub", "main", "snapshots"]
        if host.api.protocol == "rtmp":
            streams.append("ext")

        for stream in streams:
            cameras.append(ReolinkCamera(hass, config_entry, channel, stream))

    async_add_devices(cameras, update_before_add=True)


class ReolinkCamera(ReolinkCoordinatorEntity, Camera):
    """An implementation of a Reolink IP camera."""

    _attr_supported_features: CameraEntityFeature = CameraEntityFeature.STREAM

    def __init__(self, hass, config, channel, stream):
        """Initialize Reolink camera stream."""
        ReolinkCoordinatorEntity.__init__(self, hass, config)
        Camera.__init__(self)

        self._channel = channel
        self._stream = stream

        self._attr_name = f"{self._host.api.camera_name(self._channel)} {self._stream}"
        self._attr_unique_id = f"{self._host.unique_id}_{self._channel}_{self._stream}"
        self._attr_entity_registry_enabled_default = stream == "sub"

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return await self._host.api.get_stream_source(self._channel, self._stream)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        return await self._host.api.get_snapshot(self._channel)
