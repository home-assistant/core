"""
Provides functionality to interact with image processing services.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_NAME, CONF_ENTITY_ID)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import bind_hass
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.loader import get_component

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

ATTR_CONFIDENCE = 'confidence'

CONF_SOURCE = 'source'
CONF_CONFIDENCE = 'confidence'

DEFAULT_TIMEOUT = 10
DEFAULT_CONFIDENCE = 80

SOURCE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SOURCE): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
    vol.Optional(CONF_CONFIDENCE, default=DEFAULT_CONFIDENCE):
        vol.All(vol.Coerce(float), vol.Range(min=0, max=100))
})

SERVICE_SCAN_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


@bind_hass
def scan(hass, entity_id=None):
    """Force process an image."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_SCAN, data)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up image processing."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    yield from component.async_setup(config)

    @asyncio.coroutine
    def async_scan_service(service):
        """Service handler for scan."""
        image_entities = component.async_extract_from_service(service)

        update_task = [entity.async_update_ha_state(True) for
                       entity in image_entities]
        if update_task:
            yield from asyncio.wait(update_task, loop=hass.loop)

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

    @asyncio.coroutine
    def async_update(self):
        """Update image and process it.

        This method is a coroutine.
        """
        camera = get_component('camera')
        image = None

        try:
            image = yield from camera.async_get_image(
                self.hass, self.camera_entity, timeout=self.timeout)

        except HomeAssistantError as err:
            _LOGGER.error("Error on receive image from entity: %s", err)
            return

        # process image data
        yield from self.async_process_image(image)
