"""
Component that will help set the Dlib face detect processing.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.dlib_face_detect/
"""
import logging
import io
import os
import time

import voluptuous as vol

from homeassistant.core import split_entity_id, callback
# pylint: disable=unused-import
from homeassistant.components.image_processing.dlib_face_identify import (
    keep_image)
from homeassistant.components.image_processing import PLATFORM_SCHEMA  # noqa
from homeassistant.components.image_processing import (
    ATTR_ENTITY_ID, CONF_SOURCE, CONF_ENTITY_ID, CONF_NAME)
from homeassistant.components.image_processing.microsoft_face_identify import (
    ATTR_TOTAL_FACES, ImageProcessingFaceEntity)
import homeassistant.helpers.config_validation as cv


REQUIREMENTS = ['face_recognition==0.2.0']

_LOGGER = logging.getLogger(__name__)

EVENT_DETECT_FACE = 'image_processing.detect_face'

CONF_WITH_FACES = 'keep_faces'
CONF_WITHOUT_FACES = 'keep_no_faces'

DEFAULT_FACES_DIR = 'dlib_faces'
DEFAULT_WITHOUT_FACES_DIR = 'dlib_nofaces'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_WITH_FACES, default=False): cv.boolean,
    vol.Optional(CONF_WITHOUT_FACES, default=False): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Dlib Face detection platform."""
    with_faces_dir = hass.config.path(DEFAULT_FACES_DIR)
    without_faces_dir = hass.config.path(DEFAULT_WITHOUT_FACES_DIR)

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(DlibFaceDetectEntity(
            camera[CONF_ENTITY_ID],
            config[CONF_WITH_FACES],
            config[CONF_WITHOUT_FACES],
            with_faces_dir,
            without_faces_dir,
            camera.get(CONF_NAME)
        ))

    add_devices(entities)


class DlibFaceDetectEntity(ImageProcessingFaceEntity):
    """Dlib Face API entity for identify."""

    def __init__(self, camera_entity, save_faces, save_without_faces,
                 with_faces_dir, without_faces_dir, name=None):
        """Initialize Dlib face entity."""
        super().__init__()

        self._camera = camera_entity
        self._save_faces = save_faces
        self._save_without_faces = save_without_faces
        self._with_faces_dir = with_faces_dir
        self._without_faces_dir = without_faces_dir
        self.total_faces = 0

        if name:
            self._name = name
        else:
            self._name = "Dlib Face {0}".format(
                split_entity_id(camera_entity)[1])

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        attr = {
            ATTR_TOTAL_FACES: self.total_faces,
        }

        return attr

    @callback
    def async_process_faces(self, faces, total):
        """Send event with detected faces and store data."""
        # pylint: disable=unused-variable
        for face in faces:
            event = {ATTR_ENTITY_ID: self.entity_id}
            self.hass.async_add_job(
                self.hass.bus.async_fire, EVENT_DETECT_FACE, event
            )

        self.total_faces = total

    def process_image(self, image):
        """Process image."""
        # pylint: disable=import-error
        import face_recognition

        fak_file = io.BytesIO(image)
        fak_file.name = 'snapshot.jpg'
        fak_file.seek(0)

        image = face_recognition.load_image_file(fak_file)
        face_locations = face_recognition.face_locations(image)

        timestamp = time.strftime('%b-%d-%Y_%H:%M:%S', time.localtime())
        filename = "{0}_{1}.jpg".format(self.camera_entity, timestamp)

        if face_locations:
            if self._save_faces:
                keep_image(fak_file,
                           os.path.join(self._with_faces_dir, filename))
        else:
            if self._save_without_faces:
                keep_image(fak_file,
                           os.path.join(self._without_faces_dir, filename))

        self.process_faces(face_locations, len(face_locations))
