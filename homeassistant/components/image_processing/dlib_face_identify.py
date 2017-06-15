"""
Component that will help set the Dlib face detect processing.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.dlib_face_identify/
"""
import logging
import io

import voluptuous as vol

from homeassistant.core import split_entity_id
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, CONF_SOURCE, CONF_ENTITY_ID, CONF_NAME)
from homeassistant.components.image_processing.microsoft_face_identify import (
    ImageProcessingFaceEntity)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['face_recognition==0.1.14']

_LOGGER = logging.getLogger(__name__)

ATTR_NAME = 'name'
CONF_FACES = 'faces'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FACES): {cv.string: cv.isfile},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Dlib Face detection platform."""
    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(DlibFaceIdentifyEntity(
            camera[CONF_ENTITY_ID], config[CONF_FACES], camera.get(CONF_NAME)
        ))

    add_devices(entities)


class DlibFaceIdentifyEntity(ImageProcessingFaceEntity):
    """Dlib Face API entity for identify."""

    def __init__(self, camera_entity, faces, name=None):
        """Initialize Dlib face identify entry."""
        # pylint: disable=import-error
        import face_recognition
        super().__init__()

        self._camera = camera_entity

        if name:
            self._name = name
        else:
            self._name = "Dlib Face {0}".format(
                split_entity_id(camera_entity)[1])

        self._faces = {}
        for name, face_file in faces.items():
            image = face_recognition.load_image_file(face_file)
            self._faces[name] = face_recognition.face_encodings(image)[0]

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
        # pylint: disable=import-error
        import face_recognition

        fak_file = io.BytesIO(image)
        fak_file.name = 'snapshot.jpg'
        fak_file.seek(0)

        image = face_recognition.load_image_file(fak_file)
        unknowns = face_recognition.face_encodings(image)

        found = []
        for unknown_face in unknowns:
            for name, face in self._faces.items():
                result = face_recognition.compare_faces([face], unknown_face)
                if result[0]:
                    found.append({
                        ATTR_NAME: name
                    })

        self.process_faces(found, len(unknowns))
