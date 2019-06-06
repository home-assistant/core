"""Component that will help set the Microsoft face detect processing."""
import logging

import voluptuous as vol

from homeassistant.components.image_processing import (
    ATTR_AGE, ATTR_GENDER, ATTR_GLASSES, CONF_ENTITY_ID, CONF_NAME,
    CONF_SOURCE, PLATFORM_SCHEMA, ImageProcessingFaceEntity)
from homeassistant.components.microsoft_face import DATA_MICROSOFT_FACE
from homeassistant.core import split_entity_id
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SUPPORTED_ATTRIBUTES = [
    ATTR_AGE,
    ATTR_GENDER,
    ATTR_GLASSES
]

CONF_ATTRIBUTES = 'attributes'
DEFAULT_ATTRIBUTES = [ATTR_AGE, ATTR_GENDER]


def validate_attributes(list_attributes):
    """Validate face attributes."""
    for attr in list_attributes:
        if attr not in SUPPORTED_ATTRIBUTES:
            raise vol.Invalid("Invalid attribute {0}".format(attr))
    return list_attributes


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ATTRIBUTES, default=DEFAULT_ATTRIBUTES):
        vol.All(cv.ensure_list, validate_attributes),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Microsoft Face detection platform."""
    api = hass.data[DATA_MICROSOFT_FACE]
    attributes = config[CONF_ATTRIBUTES]

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(MicrosoftFaceDetectEntity(
            camera[CONF_ENTITY_ID], api, attributes, camera.get(CONF_NAME)
        ))

    async_add_entities(entities)


class MicrosoftFaceDetectEntity(ImageProcessingFaceEntity):
    """Microsoft Face API entity for identify."""

    def __init__(self, camera_entity, api, attributes, name=None):
        """Initialize Microsoft Face."""
        super().__init__()

        self._api = api
        self._camera = camera_entity
        self._attributes = attributes

        if name:
            self._name = name
        else:
            self._name = "MicrosoftFace {0}".format(
                split_entity_id(camera_entity)[1])

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_process_image(self, image):
        """Process image.

        This method is a coroutine.
        """
        face_data = None
        try:
            face_data = await self._api.call_api(
                'post', 'detect', image, binary=True,
                params={'returnFaceAttributes': ",".join(self._attributes)})

        except HomeAssistantError as err:
            _LOGGER.error("Can't process image on microsoft face: %s", err)
            return

        if not face_data:
            face_data = []

        faces = []
        for face in face_data:
            face_attr = {}
            for attr in self._attributes:
                if attr in face['faceAttributes']:
                    face_attr[attr] = face['faceAttributes'][attr]

            if face_attr:
                faces.append(face_attr)

        self.async_process_faces(faces, len(face_data))
