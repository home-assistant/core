"""Demo camera platform that has a fake camera."""
from pathlib import Path

from homeassistant.components.camera import SUPPORT_ON_OFF, Camera


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Demo camera platform."""
    async_add_entities([DemoCamera("Demo camera")])


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoCamera(Camera):
    """The representation of a Demo camera."""

    def __init__(self, name):
        """Initialize demo camera component."""
        super().__init__()
        self._name = name
        self._motion_status = False
        self.is_streaming = True
        self._images_index = 0

    async def async_camera_image(self):
        """Return a faked still image response."""
        self._images_index = (self._images_index + 1) % 4
        image_path = Path(__file__).parent / f"demo_{self._images_index}.jpg"

        return await self.hass.async_add_executor_job(image_path.read_bytes)

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

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

    async def async_enable_motion_detection(self):
        """Enable the Motion detection in base station (Arm)."""
        self._motion_status = True
        self.async_write_ha_state()

    async def async_disable_motion_detection(self):
        """Disable the motion detection in base station (Disarm)."""
        self._motion_status = False
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn off camera."""
        self.is_streaming = False
        self.async_write_ha_state()

    async def async_turn_on(self):
        """Turn on camera."""
        self.is_streaming = True
        self.async_write_ha_state()
