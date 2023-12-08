"""Support for the demo image processing."""
from __future__ import annotations

from homeassistant.components.image_processing import (
    FaceInformation,
    ImageProcessingFaceEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the demo image processing platform."""
    async_add_entities(
        [
            DemoImageProcessingFace("camera.demo_camera", "Demo Face"),
        ]
    )


class DemoImageProcessingFace(ImageProcessingFaceEntity):
    """Demo face identify image processing entity."""

    def __init__(self, camera_entity: str, name: str) -> None:
        """Initialize demo face image processing entity."""
        super().__init__()

        self._attr_name = name
        self._camera = camera_entity

    @property
    def camera_entity(self) -> str:
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def confidence(self) -> int:
        """Return minimum confidence for send events."""
        return 80

    def process_image(self, image: bytes) -> None:
        """Process image."""
        demo_data = [
            FaceInformation(
                confidence=98.34,
                name="Hans",
                age=16.0,
                gender="male",
            ),
            FaceInformation(name="Helena", age=28.0, gender="female"),
            FaceInformation(confidence=62.53, name="Luna"),
        ]

        self.process_faces(demo_data, 4)
