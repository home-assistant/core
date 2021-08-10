"""Support for Blink system camera."""
import logging

from homeassistant.components.camera import Camera
from homeassistant.helpers import entity_platform

from .const import DEFAULT_BRAND, DOMAIN, SERVICE_TRIGGER

_LOGGER = logging.getLogger(__name__)

ATTR_VIDEO_CLIP = "video"
ATTR_IMAGE = "image"


async def async_setup_entry(hass, config, async_add_entities):
    """Set up a Blink Camera."""
    data = hass.data[DOMAIN][config.entry_id]
    entities = [
        BlinkCamera(data, name, camera) for name, camera in data.cameras.items()
    ]

    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(SERVICE_TRIGGER, {}, "trigger_camera")


class BlinkCamera(Camera):
    """An implementation of a Blink Camera."""

    def __init__(self, data, name, camera):
        """Initialize a camera."""
        super().__init__()
        self.data = data
        self._attr_name = f"{DOMAIN} {name}"
        self._camera = camera
        self._attr_unique_id = f"{camera.serial}-camera"
        _LOGGER.debug("Initialized blink camera %s", self.name)

    @property
    def extra_state_attributes(self):
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

    def trigger_camera(self):
        """Trigger camera to take a snapshot."""
        self._camera.snap_picture()
        self.data.refresh()

    def camera_image(self):
        """Return a still image response from the camera."""
        return self._camera.image_from_cache.content
