"""
Component that performs OpenCV processes on images.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing.opencv/
"""
import asyncio
import logging

from homeassistant.components.camera import (
    PLATFORM_SCHEMA,
    Camera
)
from homeassistant.components.opencv import (
    ATTR_MATCH_COORDS,
    ATTR_MATCH_REGIONS,
    DOMAIN as OPENCV_DOMAIN,
    CLASSIFIER_GROUP_CONFIG,
    draw_regions,
    cv_image_from_bytes,
    cv_image_to_bytes
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import get_component

DEPENDENCIES = ['opencv']

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(CLASSIFIER_GROUP_CONFIG)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up an OpenCV camera."""
    if discovery_info is None:
        return

    devices = []

    for image_processor in hass.data[OPENCV_DOMAIN].image_processors.values():
        devices.append(OpenCVCamera(hass, image_processor))

    async_add_devices(devices)


class OpenCVCamera(Camera):
    """Representation of an OpenCV camera entity."""

    timeout = DEFAULT_TIMEOUT

    def __init__(self, hass, image_processor):
        """Initialize the OpenCV camera."""
        super().__init__()
        self._hass = hass
        self._name = image_processor.name
        self._camera_entity = image_processor.camera_entity
        self._image_processor_uid = image_processor.unique_id

    @property
    def name(self):
        """Return the name of the camera."""
        return self._name

    @asyncio.coroutine
    def async_camera_image(self):
        """Perform the update asynchronously."""
        camera = get_component('camera')

        try:
            image = yield from camera.async_get_image(self._hass,
                                                      self._camera_entity,
                                                      timeout=self.timeout)

        except HomeAssistantError as err:
            _LOGGER.error("Error on receive image from entity: %s", err)
            return

        result = yield from self._process_image(cv_image_from_bytes(image))

        return result

    @asyncio.coroutine
    def _process_image(self, cv_image):
        """Process the image."""
        image_processor = self._hass.data[OPENCV_DOMAIN].image_processors[
            self._image_processor_uid]

        regions = []
        for match in image_processor.matches:
            for region in match[ATTR_MATCH_REGIONS]:
                regions.append(region[ATTR_MATCH_COORDS])

        cv_result = yield from draw_regions(cv_image, regions)

        return cv_image_to_bytes(cv_result)
