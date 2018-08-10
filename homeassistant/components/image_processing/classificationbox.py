"""
Component that will perform classification of images via classiifcationbox.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.classificationbox
"""
import base64
import logging
from urllib.parse import urljoin

import requests
import voluptuous as vol

from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.components.image_processing import (
    ATTR_CONFIDENCE, PLATFORM_SCHEMA, ImageProcessingEntity, CONF_SOURCE,
    CONF_ENTITY_ID, CONF_CONFIDENCE)
from homeassistant.const import (
    ATTR_ID, ATTR_ENTITY_ID, CONF_IP_ADDRESS, CONF_PORT, CONF_PASSWORD,
    CONF_USERNAME, HTTP_OK, HTTP_UNAUTHORIZED)

_LOGGER = logging.getLogger(__name__)

ATTR_MODEL_ID = 'model_id'
ATTR_MODEL_NAME = 'model_name'
CLASSIFIER = 'classificationbox'
EVENT_IMAGE_CLASSIFICATION = 'image_processing.image_classification'
TIMEOUT = 9

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
})


def check_box_health(url, username, password):
    """Check the health of the classifier and return its id if healthy."""
    kwargs = {}
    if username:
        kwargs['auth'] = requests.auth.HTTPBasicAuth(username, password)
    try:
        response = requests.get(url, timeout=TIMEOUT, **kwargs)
        if response.status_code == HTTP_UNAUTHORIZED:
            _LOGGER.error("AuthenticationError on %s", CLASSIFIER)
            return None
        if response.status_code == HTTP_OK:
            return response.json()['hostname']
    except requests.exceptions.ConnectionError:
        _LOGGER.error("ConnectionError: Is %s running?", CLASSIFIER)
        return None


def encode_image(image):
    """base64 encode an image stream."""
    base64_img = base64.b64encode(image).decode('ascii')
    return base64_img


def get_matched_classes(classes):
    """Return the id and score of matched classes."""
    return {class_[ATTR_ID]: class_[ATTR_CONFIDENCE] for class_ in classes}


def get_models(url, username, password):
    """Return the list of models."""
    kwargs = {}
    if username:
        kwargs['auth'] = requests.auth.HTTPBasicAuth(username, password)
    try:
        response = requests.get(url, timeout=TIMEOUT, **kwargs)
        response_json = response.json()
        if response_json['success']:
            number_of_models = len(response_json['models'])
            if number_of_models == 0:
                _LOGGER.error("%s error: No models found", CLASSIFIER)
                return None
            else:
                return response_json['models']
    except requests.exceptions.ConnectionError:
        _LOGGER.error("ConnectionError: Is %s running?", CLASSIFIER)
        return None


def parse_classes(api_classes):
    """Parse the API classes data into the format required, a list of dict."""
    parsed_classes = []
    for entry in api_classes:
        class_ = {}
        class_[ATTR_ID] = entry['id']
        class_[ATTR_CONFIDENCE] = round(entry['score'] * 100.0, 2)
        parsed_classes.append(class_)
    return parsed_classes


def post_image(url, image, username, password):
    """Post an image to the classifier."""
    kwargs = {}
    if username:
        kwargs['auth'] = requests.auth.HTTPBasicAuth(username, password)
    input_json = {
        "inputs": [{
            "key": "image",
            "type": "image_base64",
            "value": encode_image(image)}]}
    try:
        response = requests.post(
            url,
            json=input_json,
            **kwargs
            )
        return response
    except requests.exceptions.ConnectionError:
        _LOGGER.error("ConnectionError: Is %s running?", CLASSIFIER)
        return None
    except ValueError:
        _LOGGER.error("Error with %s query", CLASSIFIER)
        return None


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the classifier."""
    entities = []
    ip_address = config[CONF_IP_ADDRESS]
    port = config[CONF_PORT]
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    url_health = "http://{}:{}/healthz".format(ip_address, port)
    hostname = check_box_health(url_health, username, password)
    if hostname is None:
        return

    url_models = 'http://{}:{}/{}/models'.format(ip_address, port, CLASSIFIER)
    models = get_models(url_models, username, password)
    if models:
        for model in models:
            for camera in config[CONF_SOURCE]:
                entities.append(ClassificationboxEntity(
                    ip_address,
                    port,
                    username,
                    password,
                    hostname,
                    camera[CONF_ENTITY_ID],
                    config[CONF_CONFIDENCE],
                    model['id'],
                    model['name'],
                    ))
    add_devices(entities)


class ClassificationboxEntity(ImageProcessingEntity):
    """Perform an image classification."""

    def __init__(self, ip, port, username, password, hostname, 
                 camera_entity, confidence, model_id, model_name):
        """Init with the camera and model info."""
        super().__init__()
        self._base_url = "http://{}:{}/{}/".format(ip, port, CLASSIFIER)
        self._username = username
        self._password = password
        self._hostname = hostname
        self._camera = camera_entity
        self._confidence = confidence
        self._model_id = model_id
        self._model_name = model_name
        camera_name = split_entity_id(camera_entity)[1]
        self._name = "{} {} {}".format(
            CLASSIFIER, camera_name, model_name)
        self._state = None
        self._matched = {}

    def process_image(self, image):
        """Process an image."""
        predict_url = urljoin(
            self._base_url, "models/{}/predict".format(self._model_id))
        response = post_image(predict_url, image,
                              self._username, self._password)
        if response is not None:
            response_json = response.json()
            if response_json['success']:
                classes = parse_classes(response_json['classes'])
                self._state = self.process_classes(classes)
                self._matched = get_matched_classes(classes)
            else:
                self._state = None
                self._matched = {}

    def process_classes(self, parsed_classes):
        """Send event for classes above threshold confidence."""
        state = None
        for class_ in parsed_classes:
            if class_[ATTR_CONFIDENCE] >= self._confidence:
                self.hass.bus.fire(
                    EVENT_IMAGE_CLASSIFICATION, {
                        'classifier': CLASSIFIER,
                        ATTR_ENTITY_ID: self.entity_id,
                        ATTR_MODEL_ID: self._model_id,
                        ATTR_MODEL_NAME: self._model_name,
                        ATTR_ID: class_[ATTR_ID],
                        ATTR_CONFIDENCE: class_[ATTR_CONFIDENCE],
                        })
        if parsed_classes[0][ATTR_CONFIDENCE] >= self._confidence:
            state = parsed_classes[0][ATTR_ID]
        return state

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
        """Return the classifier attributes."""
        attr = {
            ATTR_CONFIDENCE: self._confidence,
            ATTR_MODEL_ID: self._model_id,
            ATTR_MODEL_NAME: self._model_name,
            'hostname': self._hostname
            }
        attr.update(self._matched)
        return attr
