"""Support for the demo image processing."""
from __future__ import annotations

from homeassistant.components.camera import Image
from homeassistant.components.image_processing import (
    ATTR_AGE,
    ATTR_CONFIDENCE,
    ATTR_GENDER,
    ATTR_NAME,
    ImageProcessingFaceEntity,
)
from homeassistant.components.openalpr_local.image_processing import (
    ImageProcessingAlprEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the demo image processing platform."""
    add_entities(
        [
            DemoImageProcessingAlpr("camera.demo_camera", "Demo Alpr"),
            DemoImageProcessingFace("camera.demo_camera", "Demo Face"),
        ]
    )


class DemoImageProcessingAlpr(ImageProcessingAlprEntity):
    """Demo ALPR image processing entity."""

    def __init__(self, camera_entity: str, name: str) -> None:
        """Initialize demo ALPR image processing entity."""
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

    def process_image(self, image: Image) -> None:
        """Process image."""
        demo_data = {
            "AC3829": 98.3,
            "BE392034": 95.5,
            "CD02394": 93.4,
            "DF923043": 90.8,
        }

        self.process_plates(demo_data, 1)


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

    def process_image(self, image: Image) -> None:
        """Process image."""
        demo_data = [
            {
                ATTR_CONFIDENCE: 98.34,
                ATTR_NAME: "Hans",
                ATTR_AGE: 16.0,
                ATTR_GENDER: "male",
            },
            {ATTR_NAME: "Helena", ATTR_AGE: 28.0, ATTR_GENDER: "female"},
            {ATTR_CONFIDENCE: 62.53, ATTR_NAME: "Luna"},
        ]

        self.process_faces(demo_data, 4)
