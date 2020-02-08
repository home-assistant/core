"""Support for Ubiquiti's UVC cameras."""
import logging
from typing import Optional

import requests
from uvcclient.nvr import NotAuthorized, NvrError, UVCRemote
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
    addr = config[CONF_NVR]
    key = config[CONF_KEY]
    port = config[CONF_PORT]
    ssl = config[CONF_SSL]

    try:
        # Exceptions may be raised in all method calls to the nvr library.
        nvrconn = UVCRemote(addr, port, key, ssl=ssl)

        cameras = [camera["id"] for camera in nvrconn.index()]
    except NotAuthorized:
        _LOGGER.error("Authorization failure while connecting to NVR")
        return False
    except NvrError as ex:
        _LOGGER.error("NVR refuses to talk to me: %s", str(ex))
        raise PlatformNotReady
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error("Unable to connect to NVR: %s", str(ex))
        raise PlatformNotReady

    add_entities([UnifiVideoCamera(nvrconn, camera) for camera in cameras])
    return True


class UnifiVideoCamera(Camera):
    """A Ubiquiti Unifi Video Camera."""

    def __init__(self, nvr, uuid):
        """Initialize an Unifi camera."""
        super().__init__()
        self._nvr = nvr
        self._uuid = uuid
        self.update()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._caminfo["name"]

    @property
    def should_poll(self):
        """Order HA to pull the state."""
        return True

    @property
    def unique_id(self) -> Optional[str]:
        """Return camera UUID."""
        return self._uuid

    def update(self):
        """Fetch latest state from the API."""
        self._caminfo = self._nvr.get_camera(self._uuid)

    @property
    def supported_features(self):
        """Return supported features."""
        channels = self._caminfo["channels"]
        for channel in channels:
            if channel["isRtspEnabled"]:
                return SUPPORT_STREAM

        return 0

    @property
    def is_recording(self):
        """Return true if the camera is recording."""
        return self._caminfo["recordingSettings"]["fullTimeRecordEnabled"]

    @property
    def is_streaming(self):
        """Return true if the camera is recording."""
        for channel in self._caminfo["channels"]:
            if channel["isRtspEnabled"]:
                return True
        return False

    @is_streaming.setter
    def is_streaming(self, value):
        """Work around to handle is streaming."""

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return self._caminfo["recordingSettings"]["motionRecordEnabled"]

    @property
    def brand(self):
        """Return the brand of this camera."""
        return "Ubiquiti"

    @property
    def model(self):
        """Return the model of this camera."""
        return self._caminfo["model"]

    def camera_image(self):
        """Return the image of this camera."""
        return self._nvr.get_snapshot(self._uuid)

    async def stream_source(self):
        """Return the source of the stream."""
        channels = self._caminfo["channels"]
        for channel in channels:
            if channel["isRtspEnabled"]:
                return channel["rtspUris"][0]

        return None
