"""
Camera platform that receives images through HTTP POST.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/camera.push/
"""
import logging

from collections import deque
from datetime import timedelta
import voluptuous as vol

from homeassistant.components.camera import Camera, PLATFORM_SCHEMA,\
    STATE_IDLE, STATE_RECORDING
from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.core import callback
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import CONF_NAME, CONF_TIMEOUT, HTTP_BAD_REQUEST,\
    ATTR_LAST_TRIP_TIME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_BUFFER_SIZE = 'cache'
CONF_IMAGE_FIELD = 'image'

DEFAULT_NAME = "Push Camera"

BLANK_IMAGE_SIZE = (640, 480)

ATTR_FILENAME = 'filename'

REQUIREMENTS = ['pillow==5.0.0']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_BUFFER_SIZE, default=1): cv.positive_int,
    vol.Optional(CONF_TIMEOUT, default=timedelta(seconds=5)): vol.All(
        cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_IMAGE_FIELD, default='image'): cv.string,
})


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the Push Camera platform."""
    cameras = [PushCamera(config[CONF_NAME],
                          config[CONF_BUFFER_SIZE],
                          config[CONF_TIMEOUT])]

    hass.http.register_view(CameraPushReceiver(cameras,
                                               config[CONF_IMAGE_FIELD]))

    async_add_devices(cameras)


class CameraPushReceiver(HomeAssistantView):
    """Handle pushes from remote camera."""

    url = "/api/camera_push/{entity_id}"
    name = 'api:camera_push:camera_entity'

    def __init__(self, cameras, image_field):
        """Initialize CameraPushReceiver with camera entity."""
        self._cameras = cameras
        self._image = image_field

    async def post(self, request, entity_id):
        """Accept the POST from Camera."""
        try:
            (_camera,) = [camera for camera in self._cameras
                          if camera.entity_id == entity_id]
        except ValueError:
            _LOGGER.error("Unknown push camera %s", entity_id)
            return self.json_message('Unknown Push Camera',
                                     HTTP_BAD_REQUEST)

        try:
            data = await request.post()
            _LOGGER.debug("Received Camera push: %s", data[self._image])
            await _camera.update_image(data[self._image].file.read(),
                                       data[self._image].filename)
        except ValueError as v:
            _LOGGER.error("Unknown value %s", v)
            return self.json_message('Invalid POST', HTTP_BAD_REQUEST)
        except KeyError as k:
            _LOGGER.error('In your POST message %s', k)
            return self.json_message('Parameter %s missing', HTTP_BAD_REQUEST)


class PushCamera(Camera):
    """The representation of a Push camera."""

    def __init__(self, name, buffer_size, timeout):
        """Initialize push camera component."""
        super().__init__()
        self._name = name
        self._last_trip = None
        self._filename = None
        self._expired = None
        self._state = STATE_IDLE
        self._timeout = timeout
        self.queue = deque([], buffer_size)

        from PIL import Image
        import io

        image = Image.new('RGB', BLANK_IMAGE_SIZE)

        imgbuf = io.BytesIO()
        image.save(imgbuf, "JPEG")

        self.queue.append(imgbuf.getvalue())
        self._current_image = imgbuf.getvalue()

    @property
    def state(self):
        """Current state of the camera."""
        return self._state

    async def update_image(self, image, filename):
        """Update the camera image."""
        if self._state == STATE_IDLE:
            self._last_trip = dt_util.utcnow()
            self.queue.clear()

        self._state = STATE_RECORDING
        self._filename = filename
        self.queue.append(image)

        @callback
        def reset_state(now):
            """Set state to idle after no new images for a period of time."""
            self._state = STATE_IDLE
            self.async_schedule_update_ha_state()
            self._expired = None
            _LOGGER.debug("Reset state")

        if self._expired:
            self._expired()

        self._expired = async_track_point_in_utc_time(
            self.hass, reset_state, dt_util.utcnow() + self._timeout)

        self.async_schedule_update_ha_state()

    async def async_camera_image(self):
        """Return a still image response."""
        if self.queue:
            if self._state == STATE_IDLE:
                self.queue.rotate(-1)
            self._current_image = self.queue[0]

        return self._current_image

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            name: value for name, value in (
                (ATTR_LAST_TRIP_TIME, self._last_trip),
                (ATTR_FILENAME, self._filename),
            ) if value is not None
        }
