"""
Component that performs OpenCV processes on images

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
    DOMAIN as OPENCV_DOMAIN,
    CLASSIFIER_GROUP_CONFIG,
    process_image,
    draw_regions,
    cv_image_from_bytes
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import get_component


_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(CLASSIFIER_GROUP_CONFIG)


@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up an OpenCV camera."""
    devices = []

    if discovery_info is not None:
        for image_processor in hass.data[OPENCV_DOMAIN].image_processors:
            devices.append(OpenCVCamera(hass))
    else:
        devices.append(OpenCVStandAloneCamera(hass))

class OpenCVCamera(Camera):
    """Representation of an OpenCV camera entity."""
    def __init__(self, hass):
        """Initialize the OpenCV camera."""
        self._hass = hass

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

        return self._process_image(cv_image_from_bytes(image))

    def _process_image(self, cv_image):
        """Process the image."""
        self._add_regions(self, cv_image)

    def _add_regions(self, cv_image):
        """Add regions to the image."""
        # TODO : Get regions from image processor
        draw_regions(cv_image, None)


class OpenCVStandAloneCamera(OpenCVCamera):
    """Represent a standalone OpenCV camera."""
    def __init__(self, hass):
        """Initialize the OpenCV camera."""
        super().__init__(hass)

    def _process_image(self, cv_image):
        """Process the camera image."""

