"""Support for Blink system camera."""
from __future__ import annotations

from collections.abc import Mapping
import contextlib
import logging
from typing import Any

from requests.exceptions import ChunkedEncodingError
import voluptuous as vol

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILE_PATH, CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEFAULT_BRAND,
    DOMAIN,
    SERVICE_SAVE_RECENT_CLIPS,
    SERVICE_SAVE_VIDEO,
    SERVICE_TRIGGER,
)
from .coordinator import BlinkUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_VIDEO_CLIP = "video"
ATTR_IMAGE = "image"
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Blink Camera."""

    coordinator: BlinkUpdateCoordinator = hass.data[DOMAIN][config.entry_id]
    entities = [
        BlinkCamera(coordinator, name, camera)
        for name, camera in coordinator.api.cameras.items()
    ]

    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(SERVICE_TRIGGER, {}, "trigger_camera")
    platform.async_register_entity_service(
        SERVICE_SAVE_RECENT_CLIPS,
        {vol.Required(CONF_FILE_PATH): cv.string},
        "save_recent_clips",
    )
    platform.async_register_entity_service(
        SERVICE_SAVE_VIDEO,
        {vol.Required(CONF_FILENAME): cv.string},
        "save_video",
    )


class BlinkCamera(CoordinatorEntity[BlinkUpdateCoordinator], Camera):
    """An implementation of a Blink Camera."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: BlinkUpdateCoordinator, name, camera) -> None:
        """Initialize a camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._camera = camera
        self._attr_unique_id = f"{camera.serial}-camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera.serial)},
            serial_number=camera.serial,
            sw_version=camera.version,
            name=name,
            manufacturer=DEFAULT_BRAND,
            model=camera.camera_type,
        )
        _LOGGER.debug("Initialized blink camera %s", self._camera.name)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the camera attributes."""
        return self._camera.attributes

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection for the camera."""
        try:
            await self._camera.async_arm(True)

        except TimeoutError as er:
            raise HomeAssistantError("Blink failed to arm camera") from er

        self._camera.motion_enabled = True
        await self.coordinator.async_refresh()

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection for the camera."""
        try:
            await self._camera.async_arm(False)
        except TimeoutError as er:
            raise HomeAssistantError("Blink failed to disarm camera") from er

        self._camera.motion_enabled = False
        await self.coordinator.async_refresh()

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
        with contextlib.suppress(TimeoutError):
            await self._camera.snap_picture()
        self.async_write_ha_state()

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

    async def save_recent_clips(self, file_path) -> None:
        """Save multiple recent clips to output directory."""
        if not self.hass.config.is_allowed_path(file_path):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_path",
                translation_placeholders={"target": file_path},
            )

        try:
            await self._camera.save_recent_clips(output_dir=file_path)
        except OSError as err:
            raise ServiceValidationError(
                str(err),
                translation_domain=DOMAIN,
                translation_key="cant_write",
            ) from err

    async def save_video(self, filename) -> None:
        """Handle save video service calls."""
        if not self.hass.config.is_allowed_path(filename):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_path",
                translation_placeholders={"target": filename},
            )

        try:
            await self._camera.video_to_file(filename)
        except OSError as err:
            raise ServiceValidationError(
                str(err),
                translation_domain=DOMAIN,
                translation_key="cant_write",
            ) from err
