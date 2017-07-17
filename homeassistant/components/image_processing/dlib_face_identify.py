"""
Component that will help set the Dlib face detect processing.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.dlib_face_identify/
"""
import logging
import io
import os
import time

import voluptuous as vol

from homeassistant.core import split_entity_id
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, CONF_SOURCE, CONF_ENTITY_ID, CONF_NAME)
from homeassistant.components.image_processing.microsoft_face_identify import (
    ATTR_TOTAL_FACES, ATTR_FACES, ImageProcessingFaceEntity)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['face_recognition==0.2.0']

_LOGGER = logging.getLogger(__name__)

ATTR_NAME = 'name'
CONF_FACES = 'faces'
CONF_KNOWN_FACES = 'keep_known_faces'
CONF_UNKNOWN_FACES = 'keep_unknown_faces'

DEFAULT_KNOWN_FACES_DIR = 'dlib_known_faces'
DEFAULT_UNKNOWN_FACES_DIR = 'dlib_unknown_faces'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FACES): {cv.string: cv.isfile},
    vol.Optional(CONF_KNOWN_FACES, default=False): cv.boolean,
    vol.Optional(CONF_UNKNOWN_FACES, default=False): cv.boolean,
})


def keep_image(image, filename):
    """Save image for troubleshooting."""
    directory = os.path.dirname(filename)

    if not os.path.isdir(directory):
        os.mkdir(directory)

    with open(filename, 'wb') as fdb:
        fdb.write(image.getvalue())


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Dlib Face detection platform."""
    known_faces_dir = hass.config.path(DEFAULT_KNOWN_FACES_DIR)
    unknown_faces_dir = hass.config.path(DEFAULT_UNKNOWN_FACES_DIR)

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(DlibFaceIdentifyEntity(
            camera[CONF_ENTITY_ID],
            config[CONF_FACES],
            config[CONF_KNOWN_FACES],
            config[CONF_UNKNOWN_FACES],
            known_faces_dir,
            unknown_faces_dir,
            camera.get(CONF_NAME),
        ))

    add_devices(entities)


class DlibFaceIdentifyEntity(ImageProcessingFaceEntity):
    """Dlib Face API entity for identify."""

    def __init__(self, camera_entity, faces, save_known, save_unknown,
                 known_faces_dir, unknown_faces_dir, name=None):
        """Initialize Dlib face identify entry."""
        # pylint: disable=import-error
        import face_recognition
        super().__init__()

        self._camera = camera_entity
        self._save_known_faces = save_known
        self._save_unknown_faces = save_unknown
        self._known_faces_dir = known_faces_dir
        self._unknown_faces_dir = unknown_faces_dir

        if name:
            self._name = name
        else:
            self._name = "Dlib Face {0}".format(
                split_entity_id(camera_entity)[1])

        self._faces = {}
        for face_name, face_file in faces.items():
            try:
                image = face_recognition.load_image_file(face_file)
                self._faces[face_name] = \
                    face_recognition.face_encodings(image)[0]
            except IndexError as err:
                _LOGGER.error("Failed to parse %s. Error: %s", face_file, err)

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
            ATTR_FACES: [face['name'] for face in self.faces],
            ATTR_TOTAL_FACES: self.total_faces,
        }

        return attr

    def process_image(self, image):
        """Process image."""
        # pylint: disable=import-error
        import face_recognition

        fak_file = io.BytesIO(image)
        fak_file.name = 'snapshot.jpg'
        fak_file.seek(0)

        image = face_recognition.load_image_file(fak_file)
        unknowns = face_recognition.face_encodings(image)

        timestamp = time.strftime('%b-%d-%Y_%H:%M:%S', time.localtime())
        filename = "{0}_{1}.jpg".format(self.camera_entity, timestamp)

        found = []
        for unknown_face in unknowns:
            for name, face in self._faces.items():
                result = face_recognition.compare_faces([face], unknown_face)
                if result[0]:
                    found.append({
                        ATTR_NAME: name
                    })

                    if self._save_known_faces:
                        keep_image(fak_file,
                                   os.path.join(
                                       self._known_faces_dir,
                                       filename))

                if self._save_unknown_faces and not result[0]:
                    keep_image(fak_file,
                               os.path.join(self._unknown_faces_dir, filename))

        self.process_faces(found, len(unknowns))
