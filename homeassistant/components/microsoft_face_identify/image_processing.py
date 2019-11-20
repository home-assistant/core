"""Component that will help set the Microsoft face for verify processing."""
import copy
import logging

import voluptuous as vol

from homeassistant.components.image_processing import (
    ATTR_CONFIDENCE,
    CONF_CONFIDENCE,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_SOURCE,
    PLATFORM_SCHEMA,
    ImageProcessingFaceEntity,
)
from homeassistant.components.microsoft_face import DATA_MICROSOFT_FACE
from homeassistant.const import ATTR_NAME
from homeassistant.core import split_entity_id
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_GROUP = "group"
CONF_RECOGNITION_MODEL = "recognition_model"
SUPPORTED_RECOGNITION_MODELS = ["recognition_01", "recognition_02"]


def validate_recognition_model(config):
    """Validate recognition model."""
    config = copy.deepcopy(config)

    if config[CONF_RECOGNITION_MODEL] not in SUPPORTED_RECOGNITION_MODELS:
        config[CONF_RECOGNITION_MODEL] = "recognition_02"

    return config


PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Required(CONF_GROUP): cv.slugify,
                vol.Optional(
                    CONF_RECOGNITION_MODEL, default="recognition_02"
                ): cv.string,
            }
        ),
        validate_recognition_model,
    )
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Microsoft Face identify platform."""
    api = hass.data[DATA_MICROSOFT_FACE]
    face_group = config[CONF_GROUP]
    confidence = config[CONF_CONFIDENCE]
    recognition_model = config[CONF_RECOGNITION_MODEL]

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(
            MicrosoftFaceIdentifyEntity(
                camera[CONF_ENTITY_ID],
                api,
                face_group,
                confidence,
                recognition_model,
                camera.get(CONF_NAME),
            )
        )

    async_add_entities(entities)


class MicrosoftFaceIdentifyEntity(ImageProcessingFaceEntity):
    """Representation of the Microsoft Face API entity for identify."""

    def __init__(
        self, camera_entity, api, face_group, confidence, recognition_model, name=None
    ):
        """Initialize the Microsoft Face API."""
        super().__init__()

        self._api = api
        self._camera = camera_entity
        self._confidence = confidence
        self._face_group = face_group
        self._recognition_model = recognition_model
        self._detection_model = "detection" + self._recognition_model[-3:]

        if name:
            self._name = name
        else:
            self._name = "MicrosoftFace {0}".format(split_entity_id(camera_entity)[1])

    @property
    def confidence(self):
        """Return minimum confidence for send events."""
        return self._confidence

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
        detect = []
        try:
            face_data = await self._api.call_api(
                "post",
                "detect",
                image,
                binary=True,
                params={
                    "recognitionModel": self._recognition_model,
                    "detectionModel": self._detection_model,
                },
            )

            if face_data:
                face_ids = [data["faceId"] for data in face_data]
                detect = await self._api.call_api(
                    "post",
                    "identify",
                    {"faceIds": face_ids, "personGroupId": self._face_group},
                )

        except HomeAssistantError as err:
            _LOGGER.error("Can't process image on Microsoft face: %s", err)
            return

        # Parse data
        known_faces = []
        total = 0
        for face in detect:
            total += 1
            if not face["candidates"]:
                continue

            data = face["candidates"][0]
            name = ""
            for s_name, s_id in self._api.store[self._face_group].items():
                if data["personId"] == s_id:
                    name = s_name
                    break

            known_faces.append(
                {ATTR_NAME: name, ATTR_CONFIDENCE: data["confidence"] * 100}
            )

        self.async_process_faces(known_faces, total)
