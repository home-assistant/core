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
from homeassistant.core import callback
from homeassistant.components.http.view import KEY_AUTHENTICATED,\
    HomeAssistantView
from homeassistant.const import CONF_NAME, CONF_TIMEOUT,\
    HTTP_NOT_FOUND, HTTP_UNAUTHORIZED, HTTP_BAD_REQUEST
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

CONF_BUFFER_SIZE = 'buffer'
CONF_IMAGE_FIELD = 'field'
CONF_TOKEN = 'token'

DEFAULT_NAME = "Push Camera"

ATTR_FILENAME = 'filename'
ATTR_LAST_TRIP = 'last_trip'
ATTR_TOKEN = 'token'

PUSH_CAMERA_DATA = 'push_camera'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_BUFFER_SIZE, default=1): cv.positive_int,
    vol.Optional(CONF_TIMEOUT, default=timedelta(seconds=5)): vol.All(
        cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_IMAGE_FIELD, default='image'): cv.string,
    vol.Optional(CONF_TOKEN): vol.All(cv.string, vol.Length(min=8)),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Push Camera platform."""
    if PUSH_CAMERA_DATA not in hass.data:
        hass.data[PUSH_CAMERA_DATA] = {}

    cameras = [PushCamera(config[CONF_NAME],
                          config[CONF_BUFFER_SIZE],
                          config[CONF_TIMEOUT],
                          config.get(CONF_TOKEN))]

    hass.http.register_view(CameraPushReceiver(hass,
                                               config[CONF_IMAGE_FIELD]))

    async_add_entities(cameras)


class CameraPushReceiver(HomeAssistantView):
    """Handle pushes from remote camera."""

    url = "/api/camera_push/{entity_id}"
    name = 'api:camera_push:camera_entity'
    requires_auth = False

    def __init__(self, hass, image_field):
        """Initialize CameraPushReceiver with camera entity."""
        self._cameras = hass.data[PUSH_CAMERA_DATA]
        self._image = image_field

    async def post(self, request, entity_id):
        """Accept the POST from Camera."""
        _camera = self._cameras.get(entity_id)

        if _camera is None:
            _LOGGER.error("Unknown %s", entity_id)
            status = HTTP_NOT_FOUND if request[KEY_AUTHENTICATED]\
                else HTTP_UNAUTHORIZED
            return self.json_message('Unknown {}'.format(entity_id),
                                     status)

        # Supports HA authentication and token based
        # when token has been configured
        authenticated = (request[KEY_AUTHENTICATED] or
                         (_camera.token is not None and
                          request.query.get('token') == _camera.token))

        if not authenticated:
            return self.json_message(
                'Invalid authorization credentials for {}'.format(entity_id),
                HTTP_UNAUTHORIZED)

        try:
            data = await request.post()
            _LOGGER.debug("Received Camera push: %s", data[self._image])
            await _camera.update_image(data[self._image].file.read(),
                                       data[self._image].filename)
        except ValueError as value_error:
            _LOGGER.error("Unknown value %s", value_error)
            return self.json_message('Invalid POST', HTTP_BAD_REQUEST)
        except KeyError as key_error:
            _LOGGER.error('In your POST message %s', key_error)
            return self.json_message('{} missing'.format(self._image),
                                     HTTP_BAD_REQUEST)


class PushCamera(Camera):
    """The representation of a Push camera."""

    def __init__(self, name, buffer_size, timeout, token):
        """Initialize push camera component."""
        super().__init__()
        self._name = name
        self._last_trip = None
        self._filename = None
        self._expired_listener = None
        self._state = STATE_IDLE
        self._timeout = timeout
        self.queue = deque([], buffer_size)
        self._current_image = None
        self.token = token

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[PUSH_CAMERA_DATA][self.entity_id] = self

    @property
    def state(self):
        """Return current state of the camera."""
        return self._state

    async def update_image(self, image, filename):
        """Update the camera image."""
        if self._state == STATE_IDLE:
            self._state = STATE_RECORDING
            self._last_trip = dt_util.utcnow()
            self.queue.clear()

        self._filename = filename
        self.queue.appendleft(image)

        @callback
        def reset_state(now):
            """Set state to idle after no new images for a period of time."""
            self._state = STATE_IDLE
            self._expired_listener = None
            _LOGGER.debug("Reset state")
            self.async_schedule_update_ha_state()

        if self._expired_listener:
            self._expired_listener()

        self._expired_listener = async_track_point_in_utc_time(
            self.hass, reset_state, dt_util.utcnow() + self._timeout)

        self.async_schedule_update_ha_state()

    async def async_camera_image(self):
        """Return a still image response."""
        if self.queue:
            if self._state == STATE_IDLE:
                self.queue.rotate(1)
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
                (ATTR_LAST_TRIP, self._last_trip),
                (ATTR_FILENAME, self._filename),
                (ATTR_TOKEN, self.token),
            ) if value is not None
        }
