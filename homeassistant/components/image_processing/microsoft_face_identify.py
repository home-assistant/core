"""
Component that will help set the microsoft face for verify processing.

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

EVENT_IDENTIFY_FACE = 'identify_face'

ATTR_NAME = 'name'
ATTR_TOTAL_FACES = 'total_faces'
ATTR_KNOWN_FACES = 'known_faces'
CONF_GROUP = 'group'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_GROUP): cv.slugify,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the microsoft face identify platform."""
    api = hass.data[DATA_MICROSOFT_FACE]
    face_group = config[CONF_GROUP]
    confidence = config[CONF_CONFIDENCE]

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(MicrosoftFaceIdentifyEntity(
            camera[CONF_ENTITY_ID], api, face_group, confidence,
            camera.get(CONF_NAME)
        ))

    yield from async_add_devices(entities)


class ImageProcessingFaceIdentifyEntity(ImageProcessingEntity):
    """Base entity class for face identify/verify image processing."""

    def __init__(self):
        """Initialize base face identify/verify entity."""
        self.known_faces = {}  # last scan data
        self.total_faces = 0  # face count

    @property
    def state(self):
        """Return the state of the entity."""
        confidence = 0
        face_name = STATE_UNKNOWN

        # search high verify face
        for i_name, i_co in self.known_faces.items():
            if i_co > confidence:
                confidence = i_co
                face_name = i_name
        return face_name

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        attr = {
            ATTR_KNOWN_FACES: self.known_faces,
            ATTR_TOTAL_FACES: self.total_faces,
        }

        return attr

    def process_faces(self, known, total):
        """Send event with detected faces and store data."""
        run_callback_threadsafe(
            self.hass.loop, self.async_process_faces, known, total
        ).result()

    @callback
    def async_process_faces(self, known, total):
        """Send event with detected faces and store data.

        known are a dict in follow format:
          { 'name': confidence }

        This method must be run in the event loop.
        """
        detect = {name: confidence for name, confidence in known.items()
                  if confidence >= self.confidence}

        # send events
        for name, confidence in detect.items():
            self.hass.async_add_job(
                self.hass.bus.async_fire, EVENT_IDENTIFY_FACE, {
                    ATTR_NAME: name,
                    ATTR_ENTITY_ID: self.entity_id,
                    ATTR_CONFIDENCE: confidence,
                }
            )

        # update entity store
        self.known_faces = detect
        self.total_faces = total


class MicrosoftFaceIdentifyEntity(ImageProcessingFaceIdentifyEntity):
    """Microsoft face api entity for identify."""

    def __init__(self, camera_entity, api, face_group, confidence, name=None):
        """Initialize openalpr local api."""
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

            if face_data is None:
                return

            face_ids = [data['faceId'] for data in face_data]
            detect = yield from self._api.call_api(
                'post', 'identify',
                {'faceIds': face_ids, 'personGroupId': self._face_group})

        except HomeAssistantError as err:
            _LOGGER.error("Can't process image on microsoft face: %s", err)
            return

        # parse data
        knwon_faces = {}
        total = 0
        for face in detect:
            total += 1
            if len(face['candidates']) == 0:
                continue

            data = face['candidates'][0]
            name = ''
            for s_name, s_id in self._api.store[self._face_group].items():
                if data['personId'] == s_id:
                    name = s_name
                    break

            knwon_faces[name] = data['confidence'] * 100

        # process data
        self.async_process_faces(knwon_faces, total)
