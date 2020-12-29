"""Support for Nest Cameras."""
from datetime import timedelta
import logging

import requests

from homeassistant.components import nest
from homeassistant.components.camera import PLATFORM_SCHEMA, SUPPORT_ON_OFF, Camera
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

NEST_BRAND = "Nest"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Nest Cam.

    No longer in use.
    """


async def async_setup_legacy_entry(hass, entry, async_add_entities):
    """Set up a Nest sensor based on a config entry."""
    camera_devices = await hass.async_add_executor_job(
        hass.data[nest.DATA_NEST].cameras
    )
    cameras = [NestCamera(structure, device) for structure, device in camera_devices]
    async_add_entities(cameras, True)


class NestCamera(Camera):
    """Representation of a Nest Camera."""

    def __init__(self, structure, device):
        """Initialize a Nest Camera."""
        super().__init__()
        self.structure = structure
        self.device = device
        self._location = None
        self._name = None
        self._online = None
        self._is_streaming = None
        self._is_video_history_enabled = False
        # Default to non-NestAware subscribed, but will be fixed during update
        self._time_between_snapshots = timedelta(seconds=30)
        self._last_image = None
        self._next_snapshot_at = None

    @property
    def name(self):
        """Return the name of the nest, if any."""
        return self._name

    @property
    def unique_id(self):
        """Return the serial number."""
        return self.device.device_id

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(nest.DOMAIN, self.device.device_id)},
            "name": self.device.name_long,
            "manufacturer": "Nest Labs",
            "model": "Camera",
        }

    @property
    def should_poll(self):
        """Nest camera should poll periodically."""
        return True

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._is_streaming

    @property
    def brand(self):
        """Return the brand of the camera."""
        return NEST_BRAND

    @property
    def supported_features(self):
        """Nest Cam support turn on and off."""
        return SUPPORT_ON_OFF

    @property
    def is_on(self):
        """Return true if on."""
        return self._online and self._is_streaming

    def turn_off(self):
        """Turn off camera."""
        _LOGGER.debug("Turn off camera %s", self._name)
        # Calling Nest API in is_streaming setter.
        # device.is_streaming would not immediately change until the process
        # finished in Nest Cam.
        self.device.is_streaming = False

    def turn_on(self):
        """Turn on camera."""
        if not self._online:
            _LOGGER.error("Camera %s is offline", self._name)
            return

        _LOGGER.debug("Turn on camera %s", self._name)
        # Calling Nest API in is_streaming setter.
        # device.is_streaming would not immediately change until the process
        # finished in Nest Cam.
        self.device.is_streaming = True

    def update(self):
        """Cache value from Python-nest."""
        self._location = self.device.where
        self._name = self.device.name
        self._online = self.device.online
        self._is_streaming = self.device.is_streaming
        self._is_video_history_enabled = self.device.is_video_history_enabled

        if self._is_video_history_enabled:
            # NestAware allowed 10/min
            self._time_between_snapshots = timedelta(seconds=6)
        else:
            # Otherwise, 2/min
            self._time_between_snapshots = timedelta(seconds=30)

    def _ready_for_snapshot(self, now):
        return self._next_snapshot_at is None or now > self._next_snapshot_at

    def camera_image(self):
        """Return a still image response from the camera."""
        now = utcnow()
        if self._ready_for_snapshot(now):
            url = self.device.snapshot_url

            try:
                response = requests.get(url)
            except requests.exceptions.RequestException as error:
                _LOGGER.error("Error getting camera image: %s", error)
                return None

            self._next_snapshot_at = now + self._time_between_snapshots
            self._last_image = response.content

        return self._last_image
