"""
Component that will perform facial detection and identification via facebox.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.facebox
"""
import base64
import logging

import requests
import voluptuous as vol

from homeassistant.const import ATTR_NAME
from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingFaceEntity, ATTR_CONFIDENCE, CONF_SOURCE,
    CONF_ENTITY_ID, CONF_NAME)
from homeassistant.const import (CONF_IP_ADDRESS, CONF_PORT)

_LOGGER = logging.getLogger(__name__)

ATTR_BOUNDING_BOX = 'bounding_box'
ATTR_IMAGE_ID = 'image_id'
ATTR_MATCHED = 'matched'
CLASSIFIER = 'facebox'
TIMEOUT = 9


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_PORT): cv.port,
})


def encode_image(image):
    """base64 encode an image stream."""
    base64_img = base64.b64encode(image).decode('ascii')
    return base64_img


def get_matched_faces(faces):
    """Return the name and rounded confidence of matched faces."""
    return {face['name']: round(face['confidence'], 2)
            for face in faces if face['matched']}


def parse_faces(api_faces):
    """Parse the API face data into the format required."""
    known_faces = []
    for entry in api_faces:
        face = {}
        if entry['matched']:  # This data is only in matched faces.
            face[ATTR_NAME] = entry['name']
            face[ATTR_IMAGE_ID] = entry['id']
        else:  # Lets be explicit.
            face[ATTR_NAME] = None
            face[ATTR_IMAGE_ID] = None
        face[ATTR_CONFIDENCE] = round(100.0*entry['confidence'], 2)
        face[ATTR_MATCHED] = entry['matched']
        face[ATTR_BOUNDING_BOX] = entry['rect']
        known_faces.append(face)
    return known_faces


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the classifier."""
    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(FaceClassifyEntity(
            config[CONF_IP_ADDRESS],
            config[CONF_PORT],
            camera[CONF_ENTITY_ID],
            camera.get(CONF_NAME)
        ))
    add_devices(entities)


class FaceClassifyEntity(ImageProcessingFaceEntity):
    """Perform a face classification."""

    def __init__(self, ip, port, camera_entity, name=None):
        """Init with the API key and model id."""
        super().__init__()
        self._url = "http://{}:{}/{}/check".format(ip, port, CLASSIFIER)
        self._camera = camera_entity
        if name:
            self._name = name
        else:
            camera_name = split_entity_id(camera_entity)[1]
            self._name = "{} {}".format(
                CLASSIFIER, camera_name)
        self._matched = {}

    def process_image(self, image):
        """Process an image."""
        response = {}
        try:
            response = requests.post(
                self._url,
                json={"base64": encode_image(image)},
                timeout=TIMEOUT
                ).json()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("ConnectionError: Is %s running?", CLASSIFIER)
            response['success'] = False

        if response['success']:
            total_faces = response['facesCount']
            faces = parse_faces(response['faces'])
            self._matched = get_matched_faces(faces)
            self.process_faces(faces, total_faces)

        else:
            self.total_faces = None
            self.faces = []
            self._matched = {}

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the classifier attributes."""
        return {
            'matched_faces': self._matched,
            }
