"""Support for Ubiquiti's UVC cameras."""
import logging
from typing import Optional

import requests
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, SUPPORT_STREAM, Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

from . import CONF_KEY, CONF_NVR, CONF_PORT, CONF_SSL, DEFAULT_PORT, DEFAULT_SSL

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NVR): cv.string,
        vol.Required(CONF_KEY): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up camera entry."""
    return setup_platform(hass, entry.data, async_add_entities)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Discover cameras on a Unifi NVR."""
    try:
        cameras = [
            camera
            for camera in requests.get(
                f"{'http' if not config[CONF_SSL] else 'https'}://{config[CONF_NVR]}:{config[CONF_PORT]}/api/2.0/camera/?apiKey={config[CONF_KEY]}"
            ).json()["data"]
            if camera["managed"]
        ]

    except requests.exceptions.RequestException as ex:
        _LOGGER.error("Connection error: %s", str(ex))
        raise PlatformNotReady

    add_entities([UnifiVideoCamera(config, camera) for camera in cameras])
    return True


class UnifiVideoCamera(Camera):
    """A Ubiquiti Unifi Video Camera."""

    def __init__(self, config, camera):
        """Initialize an Unifi camera."""
        super().__init__()
        self._config = config
        self._camera = camera

    @property
    def name(self):
        """Return the name of this camera."""
        return self._camera["name"]

    @property
    def should_poll(self):
        """Order HA to pull the state."""
        return True

    @property
    def unique_id(self) -> Optional[str]:
        """Return camera UUID."""
        return self._camera["_id"]

    def update(self):
        """Fetch latest state from the API."""
        self._camera = requests.get(
            f"{'http' if not self._config[CONF_SSL] else 'https'}://{self._config[CONF_NVR]}:{self._config[CONF_PORT]}/api/2.0/camera/{self.unique_id}?apiKey={self._config[CONF_KEY]}"
        ).json()["data"][0]

    @property
    def supported_features(self):
        """Return supported features."""
        for channel in self._camera["channels"]:
            if channel["isRtspEnabled"]:
                return SUPPORT_STREAM

        return 0

    @property
    def is_recording(self):
        """Return true if the camera is recording."""
        return self._camera["recordingSettings"]["fullTimeRecordEnabled"]

    @property
    def is_streaming(self):
        """Return true if the camera is recording."""
        for channel in self._camera["channels"]:
            if channel["isRtspEnabled"]:
                return True
        return False

    @is_streaming.setter
    def is_streaming(self, value):
        """Work around to handle is streaming."""

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return self._camera["recordingSettings"]["motionRecordEnabled"]

    @property
    def brand(self):
        """Return the brand of this camera."""
        return "Ubiquiti"

    @property
    def model(self):
        """Return the model of this camera."""
        return self._camera["model"]

    def camera_image(self):
        """Return the image of this camera."""
        return requests.get(
            f"{'http' if not self._config[CONF_SSL] else 'https'}://{self._config[CONF_NVR]}:{self._config[CONF_PORT]}/api/2.0/snapshot/camera/{self.unique_id}?force=true&apiKey={self._config[CONF_KEY]}"
        ).content

    async def stream_source(self):
        """Return the source of the stream."""
        for channel in self._camera["channels"]:
            if channel["isRtspEnabled"]:
                return channel["rtspUris"][0]

        return None
