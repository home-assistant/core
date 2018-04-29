"""
Component that will perform facial recognition via a local machinebox instance.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.facebox
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
    CONF_NAME, ImageProcessingEntity)

_LOGGER = logging.getLogger(__name__)

CONF_ENDPOINT = 'endpoint'
ROUNDING_DECIMALS = 2

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENDPOINT): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the classifier."""
    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(Facebox(
            camera.get(CONF_NAME),
            config[CONF_ENDPOINT],
            camera[CONF_ENTITY_ID],
        ))
    add_devices(entities)


class Facebox(ImageProcessingEntity):
    """Perform a classification via a Facebox."""

    def __init__(self, name, endpoint, camera_entity):
        """Init with the API key and model id"""
        super().__init__()
        if name:  # Since name is optional.
            self._name = name
        else:
            self._name = "Facebox {0}".format(
                split_entity_id(camera_entity)[1])
        self._camera = camera_entity
        self._url = "http://{}/facebox/check".format(endpoint)
        self._state = "No_processing_performed"
        self._faces = {}
        self._response_time = None

    def process_image(self, image):
        """Process an image."""
        timer_start = time.perf_counter()
        response = requests.post(
            self._url,
            json=self.encode_image(image)
            ).json()

        if response['success']:
            elapsed_time = time.perf_counter() - timer_start
            self._response_time = "{} seconds".format(
                    str(round(elapsed_time, 1)))
            self._state = int(response['facesCount'])
            self._faces = self.process_faces(response)
        else:
            self._state = "Processing_not_successful"
            self._faces = {}

    def encode_image(self, image):
        """base64 encode an image stream."""
        base64_img = base64.b64encode(image).decode('ascii')
        return {"base64": base64_img}

    def process_faces(self, response):
        """Process face data from facebox response."""
        faces = {face['name']: round(face['confidence'], ROUNDING_DECIMALS)
                 for face in response['faces'] if face['matched']}
        return faces

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        attr = self._faces
        attr.update({'response_time': self._response_time})
        return attr

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if isinstance(self._state, int):
            if self._state == 1:
                unit_of_measurement = "face"
            else:
                unit_of_measurement = "faces"
        else:
            unit_of_measurement = None
        return unit_of_measurement
