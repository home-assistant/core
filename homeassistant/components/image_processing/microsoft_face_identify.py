"""
Component that will help set the Microsoft face for verify processing.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing.microsoft_face_identify/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import split_entity_id, callback
from homeassistant.const import STATE_UNKNOWN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.microsoft_face import DATA_MICROSOFT_FACE
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingEntity, CONF_CONFIDENCE, CONF_SOURCE,
    CONF_ENTITY_ID, CONF_NAME, ATTR_ENTITY_ID, ATTR_CONFIDENCE)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.async import run_callback_threadsafe

DEPENDENCIES = ['microsoft_face']

_LOGGER = logging.getLogger(__name__)

EVENT_DETECT_FACE = 'image_processing.detect_face'

ATTR_NAME = 'name'
ATTR_TOTAL_FACES = 'total_faces'
ATTR_AGE = 'age'
ATTR_GENDER = 'gender'
ATTR_MOTION = 'motion'
ATTR_GLASSES = 'glasses'
ATTR_FACES = 'faces'

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


class ImageProcessingFaceEntity(ImageProcessingEntity):
    """Base entity class for face image processing."""

    def __init__(self):
        """Initialize base face identify/verify entity."""
        self.faces = []
        self.total_faces = 0

    @property
    def state(self):
        """Return the state of the entity."""
        confidence = 0
        state = STATE_UNKNOWN

        # No confidence support
        if not self.confidence:
            return self.total_faces

        # Search high confidence
        for face in self.faces:
            if ATTR_CONFIDENCE not in face:
                continue

            f_co = face[ATTR_CONFIDENCE]
            if f_co > confidence:
                confidence = f_co
                for attr in [ATTR_NAME, ATTR_MOTION]:
                    if attr in face:
                        state = face[attr]
                        break

        return state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'face'

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        attr = {
            ATTR_FACES: self.faces,
            ATTR_TOTAL_FACES: self.total_faces,
        }

        return attr

    def process_faces(self, faces, total):
        """Send event with detected faces and store data."""
        run_callback_threadsafe(
            self.hass.loop, self.async_process_faces, faces, total).result()

    @callback
    def async_process_faces(self, faces, total):
        """Send event with detected faces and store data.

        known are a dict in follow format:
         [
           {
              ATTR_CONFIDENCE: 80,
              ATTR_NAME: 'Name',
              ATTR_AGE: 12.0,
              ATTR_GENDER: 'man',
              ATTR_MOTION: 'smile',
              ATTR_GLASSES: 'sunglasses'
           },
         ]

        This method must be run in the event loop.
        """
        # Send events
        for face in faces:
            if ATTR_CONFIDENCE in face and self.confidence:
                if face[ATTR_CONFIDENCE] < self.confidence:
                    continue

            face.update({ATTR_ENTITY_ID: self.entity_id})
            self.hass.async_add_job(
                self.hass.bus.async_fire, EVENT_DETECT_FACE, face
            )

        # Update entity store
        self.faces = faces
        self.total_faces = total


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
        knwon_faces = []
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

            knwon_faces.append({
                ATTR_NAME: name,
                ATTR_CONFIDENCE: data['confidence'] * 100,
            })

        self.async_process_faces(knwon_faces, total)
