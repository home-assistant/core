"""Component that will help set the Microsoft face detect processing."""
import copy
import logging

import voluptuous as vol

from homeassistant.components.image_processing import (
    ATTR_AGE,
    ATTR_GENDER,
    ATTR_GLASSES,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_SOURCE,
    PLATFORM_SCHEMA,
    ImageProcessingFaceEntity,
)
from homeassistant.components.microsoft_face import DATA_MICROSOFT_FACE
from homeassistant.core import split_entity_id
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SUPPORTED_ATTRIBUTES = [ATTR_AGE, ATTR_GENDER, ATTR_GLASSES]

CONF_ATTRIBUTES = "attributes"
DEFAULT_ATTRIBUTES = [ATTR_AGE, ATTR_GENDER]
CONF_RECOGNITION_MODEL = "recognition_model"
SUPPORTED_RECOGNITION_MODELS = ["recognition_01", "recognition_02"]


def validate_attributes(list_attributes):
    """Validate face attributes."""
    for attr in list_attributes:
        if attr not in SUPPORTED_ATTRIBUTES:
            raise vol.Invalid(f"Invalid attribute {attr}")
    return list_attributes


def validate_recognition_model(config):
    """Validate recognition model."""
    config = copy.deepcopy(config)

    if config[CONF_RECOGNITION_MODEL] not in SUPPORTED_RECOGNITION_MODELS:
        config[CONF_RECOGNITION_MODEL] = "recognition_02"

    _LOGGER.warning("recognition model %s", config[CONF_RECOGNITION_MODEL])
    return config


PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Optional(
                    CONF_RECOGNITION_MODEL, default="recognition_02"
                ): cv.string,
                vol.Optional(CONF_ATTRIBUTES, default=DEFAULT_ATTRIBUTES): vol.All(
                    cv.ensure_list, validate_attributes
                ),
            }
        ),
        validate_recognition_model,
    )
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Microsoft Face detection platform."""
    api = hass.data[DATA_MICROSOFT_FACE]
    attributes = config[CONF_ATTRIBUTES]
    recognition_model = config[CONF_RECOGNITION_MODEL]

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(
            MicrosoftFaceDetectEntity(
                camera[CONF_ENTITY_ID],
                api,
                attributes,
                recognition_model,
                camera.get(CONF_NAME),
            )
        )

    async_add_entities(entities)


class MicrosoftFaceDetectEntity(ImageProcessingFaceEntity):
    """Microsoft Face API entity for identify."""

    def __init__(self, camera_entity, api, attributes, recognition_model, name=None):
        """Initialize Microsoft Face."""
        super().__init__()

        self._api = api
        self._camera = camera_entity
        self._attributes = attributes
        self._recognition_model = recognition_model
        self._detection_model = "detection" + self._recognition_model[-3:]

        if name:
            self._name = name
        else:
            self._name = "MicrosoftFace {0}".format(split_entity_id(camera_entity)[1])

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def recognition_model(self):
        """Return the recognition model of the entity."""
        return self._recognition_model

    @property
    def detection_model(self):
        """Return the detection model of the entity."""
        return self._detection_model

    async def async_process_image(self, image):
        """Process image.

        This method is a coroutine.
        """
        face_data = None
        try:
            face_data = await self._api.call_api(
                "post",
                "detect",
                image,
                binary=True,
                params={
                    "returnFaceAttributes": ",".join(self._attributes),
                    "recognitionModel": self._recognition_model,
                    "detectionModel": self._detection_model,
                },
            )

        except HomeAssistantError as err:
            _LOGGER.error("Can't process image on microsoft face: %s", err)
            return

        if not face_data:
            face_data = []

        faces = []
        for face in face_data:
            face_attr = {}
            for attr in self._attributes:
                if attr in face["faceAttributes"]:
                    face_attr[attr] = face["faceAttributes"][attr]

            if face_attr:
                faces.append(face_attr)

        self.async_process_faces(faces, len(face_data))
