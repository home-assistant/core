"""Support for Vivotek IP Cameras."""

import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_AUTHENTICATION,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    CONF_VERIFY_SSL,
    CONF_IP_ADDRESS,
)
from homeassistant.components.camera import (
    PLATFORM_SCHEMA,
    DEFAULT_CONTENT_TYPE,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util.async_ import run_coroutine_threadsafe

_LOGGER = logging.getLogger(__name__)

CONF_CONTENT_TYPE = "content_type"
CONF_LIMIT_REFETCH_TO_URL_CHANGE = "limit_refetch_to_url_change"
CONF_STREAM_SOURCE = "stream_source"
CONF_FRAMERATE = "framerate"

DEFAULT_NAME = "Vivotek Camera"
DEFAULT_EVENT_0_KEY = "event_i0_enable"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_STREAM_SOURCE, default=None): vol.Any(None, cv.string),
        vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_LIMIT_REFETCH_TO_URL_CHANGE, default=False): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_CONTENT_TYPE, default=DEFAULT_CONTENT_TYPE): cv.string,
        vol.Optional(CONF_FRAMERATE, default=2): cv.positive_int,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

STATE_DETECTING_MOTION = "detecting motion"
STATE_IDLE = "idle"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a generic IP Camera."""
    async_add_entities([VivotekCamera(hass, config)])


class VivotekCamera(Camera):
    """A Vivotek IP camera."""

    def __init__(self, hass, device_info):
        """Initialize a generic camera."""
        from libpyvivotek import VivotekCamera

        super().__init__()

        self.hass = hass

        self._name = device_info.get(CONF_NAME)
        self._limit_refetch = device_info[CONF_LIMIT_REFETCH_TO_URL_CHANGE]
        self._frame_interval = 1 / device_info[CONF_FRAMERATE]
        self.content_type = device_info[CONF_CONTENT_TYPE]
        self.verify_ssl = device_info[CONF_VERIFY_SSL]
        self._event_i0_status = None
        self._event_0_key = DEFAULT_EVENT_0_KEY

        username = device_info.get(CONF_USERNAME)
        password = device_info.get(CONF_PASSWORD)

        if device_info[CONF_STREAM_SOURCE]:
            self._stream_source = (
                "rtsp://%s:%s@%s:554/live.sdp",
                username,
                password,
                device_info[CONF_STREAM_SOURCE],
            )
        else:
            self._stream_source = None

        self._brand = "Vivotek"

        self._supported_features = SUPPORT_STREAM if self._stream_source else 0

        self._last_url = None
        self._last_image = None

        self._cam = VivotekCamera(
            host=device_info.get(CONF_IP_ADDRESS),
            port=443,
            verify_ssl=device_info[CONF_VERIFY_SSL],
            usr=username,
            pwd=password,
        )

        self._motion_detection_enabled = self.event_enabled(self._event_0_key)

    @property
    def supported_features(self):
        """Return supported features for this camera."""
        return self._supported_features

    @property
    def frame_interval(self):
        """Return the interval between frames of the mjpeg stream."""
        return self._frame_interval

    def event_enabled(self, event_key):
        """Return true if event for the provided key is enabled."""
        response = self._cam.get_param(event_key)
        return int(response.replace("'", "")) == 1

    def camera_image(self):
        """Return bytes of camera image."""
        return run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop
        ).result()

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        return self._cam.snapshot()

    @property
    def name(self):
        """Return the name of this device."""
        return self._name

    async def stream_source(self):
        """Return the source of the stream."""
        return self._stream_source

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._motion_detection_enabled

    async def disable_motion_detection(self):
        """Disable motion detection in camera."""
        response = self._cam.set_param(self._event_0_key, 0)
        self._motion_detection_enabled = int(response.replace("'", "")) == 1

    async def enable_motion_detection(self):
        """Enable motion detection in camera."""
        response = self._cam.set_param(self._event_0_key, 1)
        self._motion_detection_enabled = int(response.replace("'", "")) == 1

    @property
    def brand(self):
        """Return the camera brand."""
        return self._brand

    @property
    def model(self):
        """Return the camera model."""
        return self._cam.model_name

    @property
    def state(self):
        """Return the camera state."""
        if self.motion_detection_enabled:
            return STATE_DETECTING_MOTION
        return STATE_IDLE
