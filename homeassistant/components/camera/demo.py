"""
Demo camera platform that has a fake camera.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import os
import logging
import homeassistant.util.dt as dt_util
from homeassistant.components.camera import Camera

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the Demo camera platform."""
    async_add_devices([
        DemoCamera(hass, config, 'Demo camera')
    ])


class DemoCamera(Camera):
    """The representation of a Demo camera."""

    def __init__(self, hass, config, name):
        """Initialize demo camera component."""
        super().__init__()
        self._parent = hass
        self._name = name
        self._motion_status = False

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
    def should_poll(self):
        """Camera should poll periodically."""
        return True

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return self._motion_status

    def enable_motion_detection(self):
        """Enable the Motion detection in base station (Arm)."""
        self._motion_status = True

    def disable_motion_detection(self):
        """Disable the motion detection in base station (Disarm)."""
        self._motion_status = False
