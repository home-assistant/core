"""Component for facial detection and identification via facebox."""
import base64
import logging

import requests
import voluptuous as vol

from homeassistant.components.image_processing import (
    ATTR_CONFIDENCE,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_SOURCE,
    PLATFORM_SCHEMA,
    ImageProcessingFaceEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ID,
    ATTR_NAME,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    HTTP_BAD_REQUEST,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
)
from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, SERVICE_TEACH_FACE

_LOGGER = logging.getLogger(__name__)

ATTR_BOUNDING_BOX = "bounding_box"
ATTR_CLASSIFIER = "classifier"
ATTR_IMAGE_ID = "image_id"
ATTR_MATCHED = "matched"
FACEBOX_NAME = "name"
CLASSIFIER = "facebox"
DATA_FACEBOX = "facebox_classifiers"
FILE_PATH = "file_path"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)

SERVICE_TEACH_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(FILE_PATH): cv.string,
    }
)


def check_box_health(url, username, password):
    """Check the health of the classifier and return its id if healthy."""
    kwargs = {}
    if username:
        kwargs["auth"] = requests.auth.HTTPBasicAuth(username, password)
    try:
        response = requests.get(url, **kwargs)
        if response.status_code == HTTP_UNAUTHORIZED:
            _LOGGER.error("AuthenticationError on %s", CLASSIFIER)
            return None
        if response.status_code == HTTP_OK:
            return response.json()["hostname"]
    except requests.exceptions.ConnectionError:
        _LOGGER.error("ConnectionError: Is %s running?", CLASSIFIER)
        return None


def encode_image(image):
    """base64 encode an image stream."""
    base64_img = base64.b64encode(image).decode("ascii")
    return base64_img


def get_matched_faces(faces):
    """Return the name and rounded confidence of matched faces."""
    return {
        face["name"]: round(face["confidence"], 2) for face in faces if face["matched"]
    }


def parse_faces(api_faces):
    """Parse the API face data into the format required."""
    known_faces = []
    for entry in api_faces:
        face = {}
        if entry["matched"]:  # This data is only in matched faces.
            face[FACEBOX_NAME] = entry["name"]
            face[ATTR_IMAGE_ID] = entry["id"]
        else:  # Lets be explicit.
            face[FACEBOX_NAME] = None
            face[ATTR_IMAGE_ID] = None
        face[ATTR_CONFIDENCE] = round(100.0 * entry["confidence"], 2)
        face[ATTR_MATCHED] = entry["matched"]
        face[ATTR_BOUNDING_BOX] = entry["rect"]
        known_faces.append(face)
    return known_faces


def post_image(url, image, username, password):
    """Post an image to the classifier."""
    kwargs = {}
    if username:
        kwargs["auth"] = requests.auth.HTTPBasicAuth(username, password)
    try:
        response = requests.post(url, json={"base64": encode_image(image)}, **kwargs)
        if response.status_code == HTTP_UNAUTHORIZED:
            _LOGGER.error("AuthenticationError on %s", CLASSIFIER)
            return None
        return response
    except requests.exceptions.ConnectionError:
        _LOGGER.error("ConnectionError: Is %s running?", CLASSIFIER)
        return None


def teach_file(url, name, file_path, username, password):
    """Teach the classifier a name associated with a file."""
    kwargs = {}
    if username:
        kwargs["auth"] = requests.auth.HTTPBasicAuth(username, password)
    try:
        with open(file_path, "rb") as open_file:
            response = requests.post(
                url,
                data={FACEBOX_NAME: name, ATTR_ID: file_path},
                files={"file": open_file},
                **kwargs,
            )
        if response.status_code == HTTP_UNAUTHORIZED:
            _LOGGER.error("AuthenticationError on %s", CLASSIFIER)
        elif response.status_code == HTTP_BAD_REQUEST:
            _LOGGER.error(
                "%s teaching of file %s failed with message:%s",
                CLASSIFIER,
                file_path,
                response.text,
            )
    except requests.exceptions.ConnectionError:
        _LOGGER.error("ConnectionError: Is %s running?", CLASSIFIER)


def valid_file_path(file_path):
    """Check that a file_path points to a valid file."""
    try:
        cv.isfile(file_path)
        return True
    except vol.Invalid:
        _LOGGER.error("%s error: Invalid file path: %s", CLASSIFIER, file_path)
        return False


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the classifier."""
    if DATA_FACEBOX not in hass.data:
        hass.data[DATA_FACEBOX] = []

    ip_address = config[CONF_IP_ADDRESS]
    port = config[CONF_PORT]
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    url_health = f"http://{ip_address}:{port}/healthz"
    hostname = check_box_health(url_health, username, password)
    if hostname is None:
        return

    entities = []
    for camera in config[CONF_SOURCE]:
        facebox = FaceClassifyEntity(
            ip_address,
            port,
            username,
            password,
            hostname,
            camera[CONF_ENTITY_ID],
            camera.get(CONF_NAME),
        )
        entities.append(facebox)
        hass.data[DATA_FACEBOX].append(facebox)
    add_entities(entities)

    def service_handle(service):
        """Handle for services."""
        entity_ids = service.data.get("entity_id")

        classifiers = hass.data[DATA_FACEBOX]
        if entity_ids:
            classifiers = [c for c in classifiers if c.entity_id in entity_ids]

        for classifier in classifiers:
            name = service.data.get(ATTR_NAME)
            file_path = service.data.get(FILE_PATH)
            classifier.teach(name, file_path)

    hass.services.register(
        DOMAIN, SERVICE_TEACH_FACE, service_handle, schema=SERVICE_TEACH_SCHEMA
    )


class FaceClassifyEntity(ImageProcessingFaceEntity):
    """Perform a face classification."""

    def __init__(
        self, ip_address, port, username, password, hostname, camera_entity, name=None
    ):
        """Init with the API key and model id."""
        super().__init__()
        self._url_check = f"http://{ip_address}:{port}/{CLASSIFIER}/check"
        self._url_teach = f"http://{ip_address}:{port}/{CLASSIFIER}/teach"
        self._username = username
        self._password = password
        self._hostname = hostname
        self._camera = camera_entity
        if name:
            self._name = name
        else:
            camera_name = split_entity_id(camera_entity)[1]
            self._name = f"{CLASSIFIER} {camera_name}"
        self._matched = {}

    def process_image(self, image):
        """Process an image."""
        response = post_image(self._url_check, image, self._username, self._password)
        if response:
            response_json = response.json()
            if response_json["success"]:
                total_faces = response_json["facesCount"]
                faces = parse_faces(response_json["faces"])
                self._matched = get_matched_faces(faces)
                self.process_faces(faces, total_faces)

        else:
            self.total_faces = None
            self.faces = []
            self._matched = {}

    def teach(self, name, file_path):
        """Teach classifier a face name."""
        if not self.hass.config.is_allowed_path(file_path) or not valid_file_path(
            file_path
        ):
            return
        teach_file(self._url_teach, name, file_path, self._username, self._password)

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the classifier attributes."""
        return {
            "matched_faces": self._matched,
            "total_matched_faces": len(self._matched),
            "hostname": self._hostname,
        }
