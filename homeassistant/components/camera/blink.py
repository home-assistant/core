"""
Support for Blink system camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.blink/
"""
import logging

from homeassistant.components.blink import DOMAIN, DEFAULT_BRAND
from homeassistant.components.camera import Camera

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['blink']

ATTR_VIDEO_CLIP = 'video'
ATTR_IMAGE = 'image'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Blink Camera."""
    data = hass.data[DOMAIN]
    devs = list()
    for name in data.sync.cameras:
        devs.append(BlinkCamera(hass, config, data, name))

    add_entities(devs)


class BlinkCamera(Camera):
    """An implementation of a Blink Camera."""

    def __init__(self, hass, config, data, name):
        """Initialize a camera."""
        super().__init__()
        self.data = data
        self.hass = hass
        self._name = name
        self._camera = self.data.sync.cameras[name]
        self.attr = dict()
        self.response = None
        self.current_image = None
        self.last_image = None
        _LOGGER.debug("Initialized blink camera %s", self._name)

    @property
    def name(self):
        """Return the camera name."""
        return self._name

    @property
    def state_attributes(self):
        """Return the camera attributes."""
        self.attr = self._camera.attributes
        self.attr['brand'] = self.brand
        return self.attr

    def enable_motion_detection(self):
        """Enable motion detection for the camera."""
        self._camera.set_motion_detect(True)

    def disable_motion_detection(self):
        """Disable motion detection for the camera."""
        self._camera.set_motion_detect(False)

    def motion_detection_enabled(self):
        """Return the state of the camera."""
        return self._camera.armed

    @property
    def brand(self):
        """Return the camera brand."""
        return DEFAULT_BRAND

    def camera_image(self):
        """Return a still image response from the camera."""
        return self._camera.image_from_cache.content
