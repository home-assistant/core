"""
Provides functionality to interact with image processing services.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_NAME, CONF_ENTITY_ID, CONF_NAME)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.async_ import run_callback_threadsafe

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'image_processing'
DEPENDENCIES = ['camera']

SCAN_INTERVAL = timedelta(seconds=10)

DEVICE_CLASSES = [
    'alpr',        # Automatic license plate recognition
    'face',        # Face
    'ocr',         # OCR
]

SERVICE_SCAN = 'scan'

EVENT_DETECT_FACE = 'image_processing.detect_face'

ATTR_AGE = 'age'
ATTR_CONFIDENCE = 'confidence'
ATTR_FACES = 'faces'
ATTR_GENDER = 'gender'
ATTR_GLASSES = 'glasses'
ATTR_MOTION = 'motion'
ATTR_TOTAL_FACES = 'total_faces'

CONF_SOURCE = 'source'
CONF_CONFIDENCE = 'confidence'

DEFAULT_TIMEOUT = 10
DEFAULT_CONFIDENCE = 80

SOURCE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_domain('camera'),
    vol.Optional(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SOURCE): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
    vol.Optional(CONF_CONFIDENCE, default=DEFAULT_CONFIDENCE):
        vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
})

SERVICE_SCAN_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


async def async_setup(hass, config):
    """Set up the image processing."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    await component.async_setup(config)

    async def async_scan_service(service):
        """Service handler for scan."""
        image_entities = component.async_extract_from_service(service)

        update_tasks = []
        for entity in image_entities:
            entity.async_set_context(service.context)
            update_tasks.append(
                entity.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SCAN, async_scan_service,
        schema=SERVICE_SCAN_SCHEMA)

    return True


class ImageProcessingEntity(Entity):
    """Base entity class for image processing."""

    timeout = DEFAULT_TIMEOUT

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return None

    @property
    def confidence(self):
        """Return minimum confidence for do some things."""
        return None

    def process_image(self, image):
        """Process image."""
        raise NotImplementedError()

    def async_process_image(self, image):
        """Process image.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.process_image, image)

    async def async_update(self):
        """Update image and process it.

        This method is a coroutine.
        """
        camera = self.hass.components.camera
        image = None

        try:
            image = await camera.async_get_image(
                self.camera_entity, timeout=self.timeout)

        except HomeAssistantError as err:
            _LOGGER.error("Error on receive image from entity: %s", err)
            return

        # process image data
        await self.async_process_image(image.content)


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
        state = None

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
