"""
Component that will help set the Microsoft face for verify processing.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing.microsoft_face_identify/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.microsoft_face import DATA_MICROSOFT_FACE
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingFaceEntity, ATTR_NAME,
    CONF_CONFIDENCE, CONF_SOURCE, CONF_ENTITY_ID, CONF_NAME, ATTR_CONFIDENCE)
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['microsoft_face']

_LOGGER = logging.getLogger(__name__)

CONF_GROUP = 'group'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_GROUP): cv.slugify,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Microsoft Face identify platform."""
    api = hass.data[DATA_MICROSOFT_FACE]
    face_group = config[CONF_GROUP]
    confidence = config[CONF_CONFIDENCE]

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(MicrosoftFaceIdentifyEntity(
            camera[CONF_ENTITY_ID], api, face_group, confidence,
            camera.get(CONF_NAME)
        ))

    async_add_devices(entities)


class MicrosoftFaceIdentifyEntity(ImageProcessingFaceEntity):
    """Representation of the Microsoft Face API entity for identify."""

    def __init__(self, camera_entity, api, face_group, confidence, name=None):
        """Initialize the Microsoft Face API."""
        super().__init__()

        self._api = api
        self._camera = camera_entity
        self._confidence = confidence
        self._face_group = face_group

        if name:
            self._name = name
        else:
            self._name = "MicrosoftFace {0}".format(
                split_entity_id(camera_entity)[1])

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

    @asyncio.coroutine
    def async_process_image(self, image):
        """Process image.

        This method is a coroutine.
        """
        detect = None
        try:
            face_data = yield from self._api.call_api(
                'post', 'detect', image, binary=True)

            if face_data is None or len(face_data) < 1:
                return

            face_ids = [data['faceId'] for data in face_data]
            detect = yield from self._api.call_api(
                'post', 'identify',
                {'faceIds': face_ids, 'personGroupId': self._face_group})

        except HomeAssistantError as err:
            _LOGGER.error("Can't process image on Microsoft face: %s", err)
            return

        # Parse data
        known_faces = []
        total = 0
        for face in detect:
            total += 1
            if not face['candidates']:
                continue

            data = face['candidates'][0]
            name = ''
            for s_name, s_id in self._api.store[self._face_group].items():
                if data['personId'] == s_id:
                    name = s_name
                    break

            known_faces.append({
                ATTR_NAME: name,
                ATTR_CONFIDENCE: data['confidence'] * 100,
            })

        self.async_process_faces(known_faces, total)
