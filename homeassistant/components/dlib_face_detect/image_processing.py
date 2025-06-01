"""Component that will help set the Dlib face detect processing."""

from __future__ import annotations

import io

import face_recognition

from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA as IMAGE_PROCESSING_PLATFORM_SCHEMA,
    ImageProcessingFaceEntity,
)
from homeassistant.const import ATTR_LOCATION, CONF_ENTITY_ID, CONF_NAME, CONF_SOURCE
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    split_entity_id,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN

PLATFORM_SCHEMA = IMAGE_PROCESSING_PLATFORM_SCHEMA


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Dlib Face detection platform."""
    create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_system_packages_yaml_integration_{DOMAIN}",
        breaks_in_ha_version="2025.12.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_system_packages_yaml_integration",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Dlib Face Detect",
        },
    )
    source: list[dict[str, str]] = config[CONF_SOURCE]
    add_entities(
        DlibFaceDetectEntity(camera[CONF_ENTITY_ID], camera.get(CONF_NAME))
        for camera in source
    )


class DlibFaceDetectEntity(ImageProcessingFaceEntity):
    """Dlib Face API entity for identify."""

    def __init__(self, camera_entity: str, name: str | None) -> None:
        """Initialize Dlib face entity."""
        super().__init__()

        self._attr_camera_entity = camera_entity

        if name:
            self._attr_name = name
        else:
            self._attr_name = f"Dlib Face {split_entity_id(camera_entity)[1]}"

    def process_image(self, image: bytes) -> None:
        """Process image."""

        fak_file = io.BytesIO(image)
        fak_file.name = "snapshot.jpg"
        fak_file.seek(0)

        image = face_recognition.load_image_file(fak_file)
        face_locations = face_recognition.face_locations(image)

        face_locations = [{ATTR_LOCATION: location} for location in face_locations]

        self.process_faces(face_locations, len(face_locations))
