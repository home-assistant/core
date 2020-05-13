"""Support for Blink system camera."""
import logging

from homeassistant.components.camera import Camera

from .const import DEFAULT_BRAND, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_VIDEO_CLIP = "video"
ATTR_IMAGE = "image"


async def async_setup_entry(hass, config, async_add_entities):
    """Set up a Blink Camera."""
    data = hass.data[DOMAIN][config.entry_id]
    entities = []
    for name, camera in data.cameras.items():
        entities.append(BlinkCamera(data, name, camera))

    async_add_entities(entities)


class BlinkCamera(Camera):
    """An implementation of a Blink Camera."""

    def __init__(self, data, name, camera):
        """Initialize a camera."""
        super().__init__()
        self.data = data
        self._name = f"{DOMAIN} {name}"
        self._camera = camera
        self._unique_id = f"{camera.serial}-camera"
        self.response = None
        self.current_image = None
        self.last_image = None
        _LOGGER.debug("Initialized blink camera %s", self._name)

    @property
    def name(self):
        """Return the camera name."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique camera id."""
        return self._unique_id

    @property
    def device_state_attributes(self):
        """Return the camera attributes."""
        return self._camera.attributes

    def enable_motion_detection(self):
        """Enable motion detection for the camera."""
        self._camera.set_motion_detect(True)

    def disable_motion_detection(self):
        """Disable motion detection for the camera."""
        self._camera.set_motion_detect(False)

    @property
    def motion_detection_enabled(self):
        """Return the state of the camera."""
        return self._camera.motion_enabled

    @property
    def brand(self):
        """Return the camera brand."""
        return DEFAULT_BRAND

    def camera_image(self):
        """Return a still image response from the camera."""
        return self._camera.image_from_cache.content
