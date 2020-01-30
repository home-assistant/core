"""This component provides support to the Ring Door Bell camera."""
from datetime import timedelta
import io
import logging

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.const import ATTR_ATTRIBUTION

from .const import ATTRIBUTION, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Ring Door Bell and StickUp Camera."""
    _LOGGER.debug(
        "async def async_setup_entry(hass, config_entry, async_add_entities) called"
    )
    cameras = hass.data[DOMAIN][config_entry.entry_id]["cameras"]

    async_add_entities(EagleEyeCamera(cam) for cam in cameras)


class EagleEyeCamera(Camera):
    """An implementation of a Eagle Eye camera."""

    def __init__(self, ee_camera):
        """Initialize a Ring Door Bell camera."""
        super().__init__()
        self._ee_camera = ee_camera

    @property
    def unique_id(self):
        """Return the unique id in EEN API."""
        return self._ee_camera.unique_entity_id

    @property
    def name(self):
        """Return the name of this camera."""
        return self._ee_camera.name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def camera_image(self):
        """Return bytes of camera image."""
        _LOGGER.debug("Getting live camera image for %s", self.name)
        buffer = io.BytesIO()
        self._ee_camera.get_image(buffer)
        return buffer.getvalue()

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_STREAM

    async def stream_source(self):
        """Return the stream source."""
        return self._ee_camera.get_video_url(timedelta(minutes=5))

    def turn_off(self):
        """Turn off camera."""
        raise NotImplementedError("Eagle Eye cannot be turned off")

    def turn_on(self):
        """Turn off camera."""
        raise NotImplementedError("Eagle Eye is always on")

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        raise NotImplementedError("Eagle Eye does not support motion detection")

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        raise NotImplementedError("Eagle Eye does not support motion detection")
