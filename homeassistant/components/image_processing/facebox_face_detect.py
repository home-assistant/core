"""
Component that will perform facial detection via a local facebox instance.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.facebox_face_detect
"""
import base64
import requests
import logging
import time
import voluptuous as vol

from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, CONF_SOURCE, CONF_ENTITY_ID,
    CONF_NAME)
from homeassistant.const import (CONF_IP_ADDRESS, CONF_PORT)
from homeassistant.components.image_processing.microsoft_face_identify import (
    ImageProcessingFaceEntity)

_LOGGER = logging.getLogger(__name__)

ROUNDING_DECIMALS = 2

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_PORT): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the classifier."""
    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(FaceboxFaceDetectEntity(
            config[CONF_IP_ADDRESS],
            config[CONF_PORT],
            camera[CONF_ENTITY_ID],
            camera.get(CONF_NAME)
        ))
    add_devices(entities)


class FaceboxFaceDetectEntity(ImageProcessingFaceEntity):
    """Perform a classification via a Facebox."""

    def __init__(self, ip, port, camera_entity, name=None):
        """Init with the API key and model id"""
        super().__init__()
        self._url = "http://{}:{}/facebox/check".format(ip, port)
        self._camera = camera_entity
        if name:
            self._name = name
        else:
            self._name = "Facebox {0}".format(
                split_entity_id(camera_entity)[1])
        self._response_time = None
        self.total_faces = 0
        self.faces = []

    def process_image(self, image):
        """Process an image."""
        timer_start = time.perf_counter()
        response = {}
        try:
            response = requests.post(
                self._url,
                json=self.encode_image(image),
                timeout=30
                ).json()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("ConnectionError: Is Facebox running?")
            response['success'] = False

        if response['success']:
            elapsed_time = time.perf_counter() - timer_start
            self._response_time = "{} seconds".format(
                    str(round(elapsed_time, 1)))
            self.total_faces = response['facesCount']
            self.faces = response['faces']

        else:
            self.total_faces = "Request_failed"
            self.faces = []

    def encode_image(self, image):
        """base64 encode an image stream."""
        base64_img = base64.b64encode(image).decode('ascii')
        return {"base64": base64_img}

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
        """Return the other state attributes."""
        return {
            'response_time': self._response_time,
        }
