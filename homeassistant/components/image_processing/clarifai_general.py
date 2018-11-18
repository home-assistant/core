"""
Platform that will perform image classification via Clarifai general model.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing/clarifai_general
"""
import base64
import json
import logging

import voluptuous as vol

from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingEntity, CONF_SOURCE, CONF_ENTITY_ID,
    CONF_NAME)


_LOGGER = logging.getLogger(__name__)

CLASSIFIER = 'Clarifai'
CONF_API_KEY = 'api_key'

REQUIREMENTS = ['clarifai==2.4.1']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
})


def encode_image(image):
    """base64 encode an image stream."""
    base64_img = base64.b64encode(image)
    return base64_img


def parse_concepts(api_concepts):
    """Parse the API concepts data."""
    return {concept['name']: round(100.0*concept['value'], 2)
            for concept in api_concepts}


def validate_api_key(api_key):
    """Check that an API key is valid, if yes return the app."""
    try:
        from clarifai.rest import ClarifaiApp, ApiError
        app = ClarifaiApp(api_key=api_key)
        return app
    except ApiError as exc:
        if exc.response is None:
            _LOGGER.error("%s error: setup requires an internet connection", 
            CLASSIFIER)
            return None
        else:
            error = json.loads(exc.response.content)
            _LOGGER.error(
            "%s error: %s", CLASSIFIER, error['status']['description'])
            return None


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Clarifai classifier."""
    api_key = config[CONF_API_KEY]
    app = validate_api_key(api_key)
    if app is None:
        return

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(ClarifaiClassifier(
            app,
            camera[CONF_ENTITY_ID],
            camera.get(CONF_NAME),
        ))
    add_devices(entities)


class ClarifaiClassifier(ImageProcessingEntity):
    """Perform a classification via Clarifai."""

    def __init__(self, app, camera_entity, name=None):
        """Init with the API key."""
        self.model = app.public_models.general_model
        if name:  # Since name is optional.
            self._name = name
        else:
            entity_name = split_entity_id(camera_entity)[1]
            self._name = "{} {}".format(CLASSIFIER, entity_name)
        self._camera_entity = camera_entity
        self._classifications = {}  # The dict of classifications.
        self._state = None  # The most likely classification.

    def model_prediction(self, image):
        """Make a prediction based on an image."""
        try:
            from clarifai.rest import ApiError
            response = self.model.predict_by_base64(encode_image(image))
            if response['status']['description'] == 'Ok':
                return response
        except ApiError as exc:
            if exc.response is None:
                _LOGGER.error("%s error: check your internet connection",
                CLASSIFIER)
                return None
            else:
                error = json.loads(exc.response.content)
                _LOGGER.error(
                    "%s error: %s", CLASSIFIER, error['status']['description'])
                return None

    def process_image(self, image):
        """Process an image."""
        prediction = self.model_prediction(image)

        if prediction:
            api_concepts = prediction['outputs'][0]['data']['concepts']
            self._classifications = parse_concepts(api_concepts)
            self._state = max(self._classifications,
                              key=self._classifications.get)

        else:
            self._classifications = {}
            self._state = None

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera_entity

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = self._classifications
        return attr

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name
