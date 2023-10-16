"""Support for Blink system camera."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

from requests.exceptions import ChunkedEncodingError

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_BRAND, DOMAIN, SERVICE_TRIGGER

_LOGGER = logging.getLogger(__name__)

ATTR_VIDEO_CLIP = "video"
ATTR_IMAGE = "image"


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Blink Camera."""
    data = hass.data[DOMAIN][config.entry_id]
    entities = [
        BlinkCamera(data, name, camera) for name, camera in data.cameras.items()
    ]

    async_add_entities(entities, update_before_add=True)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(SERVICE_TRIGGER, {}, "trigger_camera")


class BlinkCamera(Camera):
    """An implementation of a Blink Camera."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, data, name, camera):
        """Initialize a camera."""
        super().__init__()
        self.data = data
        self._camera = camera
        self._attr_unique_id = f"{camera.serial}-camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera.serial)},
            name=name,
            manufacturer=DEFAULT_BRAND,
            model=camera.camera_type,
        )
        _LOGGER.debug("Initialized blink camera %s", self.name)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the camera attributes."""
        return self._camera.attributes

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection for the camera."""
        try:
            await self._camera.async_arm(True)
            await self.data.refresh(force=True)
        except asyncio.TimeoutError:
            self._attr_available = False

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection for the camera."""
        try:
            await self._camera.async_arm(False)
            await self.data.refresh(force=True)
        except asyncio.TimeoutError:
            self._attr_available = False

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the state of the camera."""
        return self._camera.arm

    @property
    def brand(self) -> str | None:
        """Return the camera brand."""
        return DEFAULT_BRAND

    async def trigger_camera(self) -> None:
        """Trigger camera to take a snapshot."""
        try:
            await self._camera.snap_picture()
            self.async_schedule_update_ha_state(force_refresh=True)
        except asyncio.TimeoutError:
            pass

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        try:
            return self._camera.image_from_cache
        except ChunkedEncodingError:
            _LOGGER.debug("Could not retrieve image for %s", self._camera.name)
            return None
        except TypeError:
            _LOGGER.debug("No cached image for %s", self._camera.name)
            return None
