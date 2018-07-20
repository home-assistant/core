"""
Component that will perform facial detection and identification via facebox.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.facebox
"""
import base64
import logging

import requests
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_NAME)
from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingFaceEntity, ATTR_CONFIDENCE, CONF_SOURCE,
    CONF_ENTITY_ID, CONF_NAME, DOMAIN)
from homeassistant.const import (CONF_IP_ADDRESS, CONF_PORT)

_LOGGER = logging.getLogger(__name__)

ATTR_BOUNDING_BOX = 'bounding_box'
ATTR_CLASSIFIER = 'classifier'
ATTR_IMAGE_ID = 'image_id'
ATTR_MATCHED = 'matched'
CLASSIFIER = 'facebox'
DATA_FACEBOX = 'facebox_classifiers'
EVENT_CLASSIFIER_TEACH = 'image_processing.teach_classifier'
FILE_PATH = 'file_path'
SERVICE_TEACH_FACE = 'facebox_teach_face'
TIMEOUT = 9


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_PORT): cv.port,
})

SERVICE_TEACH_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(FILE_PATH): cv.string,
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


def post_image(url, image):
    """Post an image to the classifier."""
    try:
        response = requests.post(
            url,
            json={"base64": encode_image(image)},
            timeout=TIMEOUT
            )
        return response
    except requests.exceptions.ConnectionError:
        _LOGGER.error("ConnectionError: Is %s running?", CLASSIFIER)


def valid_file_path(file_path):
    """Check that a file_path points to a valid file."""
    try:
        cv.isfile(file_path)
        return True
    except vol.Invalid:
        _LOGGER.error(
            "%s error: Invalid file path: %s", CLASSIFIER, file_path)
        return False


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the classifier."""
    if DATA_FACEBOX not in hass.data:
        hass.data[DATA_FACEBOX] = []

    entities = []
    for camera in config[CONF_SOURCE]:
        facebox = FaceClassifyEntity(
            config[CONF_IP_ADDRESS],
            config[CONF_PORT],
            camera[CONF_ENTITY_ID],
            camera.get(CONF_NAME))
        entities.append(facebox)
        hass.data[DATA_FACEBOX].append(facebox)
    add_devices(entities)

    def service_handle(service):
        """Handle for services."""
        entity_ids = service.data.get('entity_id')

        classifiers = hass.data[DATA_FACEBOX]
        if entity_ids:
            classifiers = [c for c in classifiers if c.entity_id in entity_ids]

        for classifier in classifiers:
            name = service.data.get(ATTR_NAME)
            file_path = service.data.get(FILE_PATH)
            classifier.teach(name, file_path)

    hass.services.register(
        DOMAIN,
        SERVICE_TEACH_FACE,
        service_handle,
        schema=SERVICE_TEACH_SCHEMA)


class FaceClassifyEntity(ImageProcessingFaceEntity):
    """Perform a face classification."""

    def __init__(self, ip, port, camera_entity, name=None):
        """Init with the API key and model id."""
        super().__init__()
        self._url_check = "http://{}:{}/{}/check".format(ip, port, CLASSIFIER)
        self._url_teach = "http://{}:{}/{}/teach".format(ip, port, CLASSIFIER)
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
        response = post_image(self._url_check, image)
        if response is not None:
            response_json = response.json()
            if response_json['success']:
                total_faces = response_json['facesCount']
                faces = parse_faces(response_json['faces'])
                self._matched = get_matched_faces(faces)
                self.process_faces(faces, total_faces)

        else:
            self.total_faces = None
            self.faces = []
            self._matched = {}

    def teach(self, name, file_path):
        """Teach classifier a face name."""
        if (not self.hass.config.is_allowed_path(file_path)
                or not valid_file_path(file_path)):
            return
        with open(file_path, 'rb') as open_file:
            response = requests.post(
                self._url_teach,
                data={ATTR_NAME: name, 'id': file_path},
                files={'file': open_file})

        if response.status_code == 200:
            self.hass.bus.fire(
                EVENT_CLASSIFIER_TEACH, {
                    ATTR_CLASSIFIER: CLASSIFIER,
                    ATTR_NAME: name,
                    FILE_PATH: file_path,
                    'success': True,
                    'message': None
                    })

        elif response.status_code == 400:
            _LOGGER.warning(
                "%s teaching of file %s failed with message:%s",
                CLASSIFIER, file_path, response.text)
            self.hass.bus.fire(
                EVENT_CLASSIFIER_TEACH, {
                    ATTR_CLASSIFIER: CLASSIFIER,
                    ATTR_NAME: name,
                    FILE_PATH: file_path,
                    'success': False,
                    'message': response.text
                    })

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
            'total_matched_faces': len(self._matched),
            }
