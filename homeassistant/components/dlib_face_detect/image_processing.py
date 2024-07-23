"""Component that will help set the Dlib face detect processing."""

from __future__ import annotations

import io

import face_recognition

from homeassistant.components.image_processing import ImageProcessingFaceEntity
from homeassistant.const import ATTR_LOCATION, CONF_ENTITY_ID, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from homeassistant.components.image_processing import (  # noqa: F401, isort:skip
    PLATFORM_SCHEMA,
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Dlib Face detection platform."""
    add_entities(
        DlibFaceDetectEntity(camera[CONF_ENTITY_ID], camera.get(CONF_NAME))
        for camera in config[CONF_SOURCE]
    )


class DlibFaceDetectEntity(ImageProcessingFaceEntity):
    """Dlib Face API entity for identify."""

    def __init__(self, camera_entity, name=None):
        """Initialize Dlib face entity."""
        super().__init__()

        self._camera = camera_entity

        if name:
            self._name = name
        else:
            self._name = f"Dlib Face {split_entity_id(camera_entity)[1]}"

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def process_image(self, image):
        """Process image."""

        fak_file = io.BytesIO(image)
        fak_file.name = "snapshot.jpg"
        fak_file.seek(0)

        image = face_recognition.load_image_file(fak_file)
        face_locations = face_recognition.face_locations(image)

        face_locations = [{ATTR_LOCATION: location} for location in face_locations]

        self.process_faces(face_locations, len(face_locations))
