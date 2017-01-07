"""
Provides functionality to interact with image processing services.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing/
"""
import asyncio
from datetime import timedelta
import logging
import os

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_ENTITY_PICTURE, CONF_TIMEOUT,
    CONF_NAME, CONF_ENTITY_ID, STATE_UNKNOWN)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.async import run_callback_threadsafe

DOMAIN = 'image_processing'
DEPENDENCIES = ['camera']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

PROCESSING_CLASSES = [
    None,            # Generic
    'alpr',          # Processing licences plates
    'face',          # Processing biometric face data
]

SERVICE_SCAN = 'scan'

EVENT_FOUND_PLATE = 'found_plate'

ATTR_PLATE = 'plate'
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
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_CONFIDENCE, default=DEFAULT_CONFIDENCE):
        vol.All(vol.Coerce(float), vol.Range(min=0, max=100))
})

SERVICE_SCAN_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


def scan(hass, entity_id=None):
    """Force process a image."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_SCAN, data)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup image processing."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    yield from component.async_setup(config)

    descriptions = yield from hass.loop.run_in_executor(
        None, load_yaml_config_file,
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

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
        descriptions.get(SERVICE_SCAN), schema=SERVICE_SCAN_SCHEMA)

    return True


class ImageProcessingEntity(Entity):
    """Base entity class for image processing."""

    timeout = DEFAULT_TIMEOUT  # timeout for requests

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return None

    @property
    def processing_class(self):
        """Return the class of this entity from PROCESSING_CLASSES."""
        return None

    def process_image(self, image):
        """Process image."""
        raise NotImplementedError()

    def async_process_image(self, image):
        """Process image.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.loop.run_in_executor(None, self.process_image, image)

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        attr = {}

        if self.processing_class is not None:
            attr['processing_class'] = self.processing_class

        return attr

    @asyncio.coroutine
    def async_update(self):
        """Update image and process it.

        This method is a coroutine.
        """
        websession = async_get_clientsession(self.hass)
        state = self.hass.states.get(self.camera_entity)

        if state is None:
            _LOGGER.warning(
                "No entity '%s' for grab a image.", self.camera_entity)
            return

        url = "{0}{1}".format(
            self.hass.config.api.base_url,
            state.attributes.get(ATTR_ENTITY_PICTURE))

        response = None
        try:
            with async_timeout.timeout(10, loop=self.hass.loop):
                response = yield from websession.get(url)

                if response.status != 200:
                    _LOGGER.error("Error %d on %s", response.status, url)
                    return

                image = yield from response.read()

        except (asyncio.TimeoutError, aiohttp.errors.ClientError):
            _LOGGER.error("Can't connect to %s", url)
            return

        finally:
            if response is not None:
                yield from response.release()

        # process image data
        yield from self.async_process_image(image)


class ImageProcessingAlprEntity(ImageProcessingEntity):
    """Base entity class for alpr image processing."""

    plates = {}  # last scan data
    vehicles = 0  # vehicles count

    @property
    def confidence(self):
        """Return minimum confidence for send events."""
        return DEFAULT_CONFIDENCE

    @property
    def processing_class(self):
        """Return the class of this entity from PROCESSING_CLASSES."""
        return 'alpr'

    @property
    def state(self):
        """Return the state of the entity."""
        confidence = 0
        plate = STATE_UNKNOWN

        # search high plate
        for i_pl, i_co in self.plates.items():
            if i_co > confidence:
                confidence = i_co
                plate = i_pl
        return plate

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        attr = super().state_attributes

        attr.update({
            'plates': self.plates,
            'vehicles': self.vehicles
        })

        return attr

    def process_plates(self, plates, vehicles):
        """Send event with new plates and store data."""
        run_callback_threadsafe(
            self.hass.loop, self.async_process_plates, plates, vehicles
        ).result()

    @callback
    def async_process_plates(self, plates, vehicles):
        """Send event with new plates and store data.

        plates are a dict in follow format:
          { 'plate': confidence }

        This method must be run in the event loop.
        """
        plates = {plate: confidence for plate, confidence in plates.items()
                  if confidence >= self.confidence}
        new_plates = set(plates) - set(self.plates)

        # send events
        for i_plate in new_plates:
            self.hass.async_add_job(
                self.hass.bus.async_fire, EVENT_FOUND_PLATE, {
                    ATTR_PLATE: i_plate,
                    ATTR_ENTITY_ID: self.entity_id,
                    ATTR_CONFIDENCE: plates.get(i_plate),
                }
            )

        # update entity store
        self.plates = plates
        self.vehicles = vehicles
