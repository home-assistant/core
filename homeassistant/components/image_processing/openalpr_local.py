"""
Component that will help set the openalpr local for alpr processing.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing.openalpr_local/
"""
import asyncio
import logging
import io
import re

import voluptuous as vol

from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingAlprEntity, CONF_CONFIDENCE, CONF_SOURCE,
    CONF_ENTITY_ID, CONF_NAME)

_LOGGER = logging.getLogger(__name__)

RE_ALPR_PLATE = re.compile(r"^plate\d*:")
RE_ALPR_RESULT = re.compile(r"- (\w*)\s*confidence: (\d*.\d*)")

OPENALPR_REGIONS = [
    'us',
    'eu',
    'au',
    'auwide',
    'gb',
    'kr',
    'mx',
    'sg',
]

CONF_REGION = 'region'
CONF_ALPR_BIN = 'alp_bin'

DEFAULT_BINARY = 'alpr'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_REGION):
        vol.All(vol.Lower, vol.In(OPENALPR_REGIONS)),
    vol.Optional(CONF_ALPR_BIN, default=DEFAULT_BINARY): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the openalpr local platform."""
    command = [config[CONF_ALPR_BIN], '-c', config[CONF_REGION], '-']
    confidence = config[CONF_CONFIDENCE]

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(OpenAlprLocalEntity(
            camera[CONF_ENTITY_ID], command, confidence, camera[CONF_NAME]))

    async_add_devices(entities)


class OpenAlprLocalEntity(ImageProcessingAlprEntity):
    """OpenAlpr local api entity."""

    def __init__(self, camera_entity, command, confidence, name=None):
        """Initialize openalpr local api."""
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

    def async_process_image(self, image):
        """Process image.

        This method is a coroutine.
        """
        result = {}
        vehicles = 0

        alpr = yield from asyncio.create_subprocess_exec(
            *self._cmd,
            loop=self.hass.loop,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )

        # send image
        stdout, stderr = yield from alpr.communicate(input=image)
        stdout = io.StringIO(str(stdout, 'utf-8'))

        while True:
            line = stdout.readline()
            if not line:
                break

            new_plates = RE_ALPR_PLATE.search(line)
            new_result = RE_ALPR_RESULT.search(line)

            # found new vehicle
            if new_plates:
                vehicles += 1
                continue

            # found plate result
            if new_result:
                try:
                    result.update(
                        {new_result.group(1): float(new_result.group(2))})
                except ValueError:
                    continue

        self.async_process_plates(result, vehicles)
