"""
Component that will perform facial detection and identification via facebox.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.facebox
"""
import base64
import logging

import requests
import voluptuous as vol

from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingFaceEntity, CONF_SOURCE, CONF_ENTITY_ID,
    CONF_NAME)
from homeassistant.const import (CONF_IP_ADDRESS, CONF_PORT)

_LOGGER = logging.getLogger(__name__)

CLASSIFIER = 'facebox'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_PORT): cv.port,
})


def encode_image(image):
    """base64 encode an image stream."""
    base64_img = base64.b64encode(image).decode('ascii')
    return {"base64": base64_img}


def get_matched_faces(faces):
    """Return the name and rounded confidence of matched faces."""
    return {face['name']: round(face['confidence'], 2)
            for face in faces if face['matched']}


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
                json=encode_image(image),
                timeout=9
                ).json()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("ConnectionError: Is %s running?", CLASSIFIER)
            response['success'] = False

        if response['success']:
            faces = response['faces']
            total = response['facesCount']
            self.process_faces(faces, total)
            self._matched = get_matched_faces(faces)

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
