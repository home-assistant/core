"""Component that will help set the OpenALPR local for ALPR processing."""
import asyncio
import io
import logging
import re

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.core import split_entity_id, callback
from homeassistant.const import CONF_REGION
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingEntity, CONF_CONFIDENCE, CONF_SOURCE,
    CONF_ENTITY_ID, CONF_NAME, ATTR_ENTITY_ID, ATTR_CONFIDENCE)
from homeassistant.util.async_ import run_callback_threadsafe

_LOGGER = logging.getLogger(__name__)

RE_ALPR_PLATE = re.compile(r"^plate\d*:")
RE_ALPR_RESULT = re.compile(r"- (\w*)\s*confidence: (\d*.\d*)")

EVENT_FOUND_PLATE = 'image_processing.found_plate'

ATTR_PLATE = 'plate'
ATTR_PLATES = 'plates'
ATTR_VEHICLES = 'vehicles'

OPENALPR_REGIONS = [
    'au',
    'auwide',
    'br',
    'eu',
    'fr',
    'gb',
    'kr',
    'kr2',
    'mx',
    'sg',
    'us',
    'vn2'
]

CONF_ALPR_BIN = 'alp_bin'

DEFAULT_BINARY = 'alpr'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_REGION): vol.All(vol.Lower, vol.In(OPENALPR_REGIONS)),
    vol.Optional(CONF_ALPR_BIN, default=DEFAULT_BINARY): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the OpenALPR local platform."""
    command = [config[CONF_ALPR_BIN], '-c', config[CONF_REGION], '-']
    confidence = config[CONF_CONFIDENCE]

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(OpenAlprLocalEntity(
            camera[CONF_ENTITY_ID], command, confidence, camera.get(CONF_NAME)
        ))

    async_add_entities(entities)


class ImageProcessingAlprEntity(ImageProcessingEntity):
    """Base entity class for ALPR image processing."""

    def __init__(self):
        """Initialize base ALPR entity."""
        self.plates = {}
        self.vehicles = 0

    @property
    def state(self):
        """Return the state of the entity."""
        confidence = 0
        plate = None

        # search high plate
        for i_pl, i_co in self.plates.items():
            if i_co > confidence:
                confidence = i_co
                plate = i_pl
        return plate

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'alpr'

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        attr = {
            ATTR_PLATES: self.plates,
            ATTR_VEHICLES: self.vehicles
        }

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

        # Send events
        for i_plate in new_plates:
            self.hass.async_add_job(
                self.hass.bus.async_fire, EVENT_FOUND_PLATE, {
                    ATTR_PLATE: i_plate,
                    ATTR_ENTITY_ID: self.entity_id,
                    ATTR_CONFIDENCE: plates.get(i_plate),
                }
            )

        # Update entity store
        self.plates = plates
        self.vehicles = vehicles


class OpenAlprLocalEntity(ImageProcessingAlprEntity):
    """OpenALPR local api entity."""

    def __init__(self, camera_entity, command, confidence, name=None):
        """Initialize OpenALPR local API."""
        super().__init__()

        self._cmd = command
        self._camera = camera_entity
        self._confidence = confidence

        if name:
            self._name = name
        else:
            self._name = "OpenAlpr {0}".format(
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

    async def async_process_image(self, image):
        """Process image.

        This method is a coroutine.
        """
        result = {}
        vehicles = 0

        alpr = await asyncio.create_subprocess_exec(
            *self._cmd,
            loop=self.hass.loop,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )

        # Send image
        stdout, _ = await alpr.communicate(input=image)
        stdout = io.StringIO(str(stdout, 'utf-8'))

        while True:
            line = stdout.readline()
            if not line:
                break

            new_plates = RE_ALPR_PLATE.search(line)
            new_result = RE_ALPR_RESULT.search(line)

            # Found new vehicle
            if new_plates:
                vehicles += 1
                continue

            # Found plate result
            if new_result:
                try:
                    result.update(
                        {new_result.group(1): float(new_result.group(2))})
                except ValueError:
                    continue

        self.async_process_plates(result, vehicles)
