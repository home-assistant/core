"""
Demo camera platform that has a fake camera.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import os
import logging
import asyncio
import homeassistant.util.dt as dt_util

from homeassistant.components.camera import Camera
from homeassistant.components.camera import (MOTION_ENABLED, MOTION_DISABLED)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Demo camera platform."""
    add_devices([
        DemoCamera(hass, config, 'Demo camera')
    ])


class DemoCamera(Camera):
    """The representation of a Demo camera."""

    def __init__(self, hass, config, name):
        """Initialize demo camera component."""
        super().__init__()
        self._parent = hass
        self._name = name
        self._motion_status = MOTION_DISABLED

    def camera_image(self):
        """Return a faked still image response."""
        now = dt_util.utcnow()

        image_path = os.path.join(
            os.path.dirname(__file__), 'demo_{}.jpg'.format(now.second % 4))
        with open(image_path, 'rb') as file:
            return file.read()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def get_motion_detection_status(self):
        """Camera Motion Detection Status."""
        return self._motion_status

    @asyncio.coroutine
    def async_enable_motion_detect(self):
        """Camera arm."""
        self._motion_status = MOTION_ENABLED
        self.hass.async_add_job(self.async_update_ha_state())
        self.hass.async_add_job(self.async_update())

    @asyncio.coroutine
    def async_disable_motion_detect(self):
        """Camera disarm."""
        self._motion_status = MOTION_DISABLED
        self.hass.async_add_job(self.async_update_ha_state())
        self.hass.async_add_job(self.async_update())

    @asyncio.coroutine
    def async_update(self):
        """Perform the I/O operation with camera."""
        if self._motion_status == MOTION_ENABLED:
            _LOGGER.info("Enable Motion detection for this camera here")
        else:
            _LOGGER.info("Disable Motion detection for this camera here")
