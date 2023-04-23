"""Demo camera platform that has a fake camera."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo camera platform."""
    async_add_entities(
        [
            DemoCamera("Demo camera", "image/jpg"),
            DemoCamera("Demo camera png", "image/png"),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoCamera(Camera):
    """The representation of a Demo camera."""

    _attr_is_streaming = True
    _attr_motion_detection_enabled = False
    _attr_supported_features = CameraEntityFeature.ON_OFF

    def __init__(self, name: str, content_type: str) -> None:
        """Initialize demo camera component."""
        super().__init__()
        self._attr_name = name
        self.content_type = content_type
        self._images_index = 0

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes:
        """Return a faked still image response."""
        self._images_index = (self._images_index + 1) % 4
        ext = "jpg" if self.content_type == "image/jpg" else "png"
        image_path = Path(__file__).parent / f"demo_{self._images_index}.{ext}"

        return await self.hass.async_add_executor_job(image_path.read_bytes)

    async def async_enable_motion_detection(self) -> None:
        """Enable the Motion detection in base station (Arm)."""
        self._attr_motion_detection_enabled = True
        self.async_write_ha_state()

    async def async_disable_motion_detection(self) -> None:
        """Disable the motion detection in base station (Disarm)."""
        self._attr_motion_detection_enabled = False
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        self._attr_is_streaming = False
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn on camera."""
        self._attr_is_streaming = True
        self._attr_is_on = True
        self.async_write_ha_state()
