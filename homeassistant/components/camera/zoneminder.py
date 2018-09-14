"""
Support for ZoneMinder camera streaming.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.zoneminder/
"""
import asyncio
import logging

from homeassistant.const import CONF_NAME
from homeassistant.components.camera.mjpeg import (
    CONF_MJPEG_URL, CONF_STILL_IMAGE_URL, MjpegCamera)

from homeassistant.components import zoneminder

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zoneminder']
DOMAIN = 'zoneminder'


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up the ZoneMinder cameras."""
    zm = hass.data[DOMAIN]

    monitors = zm.get_monitors()
    if not monitors:
        _LOGGER.warning("Could not fetch monitors from ZoneMinder")
        return

    cameras = []
    for monitor in monitors:
        _LOGGER.info("Initializing camera %s", monitor.id)
        cameras.append(ZoneMinderCamera(hass, monitor))

    if not cameras:
        _LOGGER.warning("No active cameras found")
        return

    async_add_entities(cameras)


class ZoneMinderCamera(MjpegCamera):
    """Representation of a ZoneMinder Monitor Stream."""

    def __init__(self, hass, monitor):
        """Initialize as a subclass of MjpegCamera."""
        device_info = {
            CONF_NAME: monitor.name,
            CONF_MJPEG_URL: monitor.mjpeg_image_url,
            CONF_STILL_IMAGE_URL: monitor.still_image_url
        }
        super().__init__(hass, device_info)
        self._monitor_id = monitor.id
        self._is_recording = None
        self._monitor = monitor

    @property
    def should_poll(self):
        """Update the recording state periodically."""
        return True

    def update(self):
        """Update our recording state from the ZM API."""
        _LOGGER.debug("Updating camera state for monitor %i", self._monitor_id)
        self._is_recording = self._monitor.is_recording

    @property
    def is_recording(self):
        """Return whether the monitor is in alarm mode."""
        return self._is_recording
