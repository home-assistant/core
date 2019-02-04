"""
Demo camera platform that has a fake camera.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import logging
import os

from homeassistant.components.camera import Camera, SUPPORT_ON_OFF

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Demo camera platform."""
    async_add_entities([
        DemoCamera('Demo camera')
    ])


class DemoCamera(Camera):
    """The representation of a Demo camera."""

    def __init__(self, name):
        """Initialize demo camera component."""
        super().__init__()
        self._name = name
        self._motion_status = False
        self.is_streaming = True
        self._images_index = 0

    def camera_image(self):
        """Return a faked still image response."""
        self._images_index = (self._images_index + 1) % 4

        image_path = os.path.join(
            os.path.dirname(__file__),
            'demo_{}.jpg'.format(self._images_index))
        _LOGGER.debug('Loading camera_image: %s', image_path)
        with open(image_path, 'rb') as file:
            return file.read()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def should_poll(self):
        """Demo camera doesn't need poll.

        Need explicitly call schedule_update_ha_state() after state changed.
        """
        return False

    @property
    def supported_features(self):
        """Camera support turn on/off features."""
        return SUPPORT_ON_OFF

    @property
    def is_on(self):
        """Whether camera is on (streaming)."""
        return self.is_streaming

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return self._motion_status

    def enable_motion_detection(self):
        """Enable the Motion detection in base station (Arm)."""
        self._motion_status = True
        self.schedule_update_ha_state()

    def disable_motion_detection(self):
        """Disable the motion detection in base station (Disarm)."""
        self._motion_status = False
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn off camera."""
        self.is_streaming = False
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn on camera."""
        self.is_streaming = True
        self.schedule_update_ha_state()
