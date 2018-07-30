"""
Component to interface with cameras.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/camera/
"""
import asyncio
import base64
import collections
from contextlib import suppress
from datetime import timedelta
import logging
import hashlib
from random import SystemRandom

import attr
from aiohttp import web
import async_timeout
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, \
    SERVICE_TURN_ON
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import bind_hass
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.components.http import HomeAssistantView, KEY_AUTHENTICATED
from homeassistant.components import websocket_api
import homeassistant.helpers.config_validation as cv

DOMAIN = 'camera'
DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)

SERVICE_ENABLE_MOTION = 'enable_motion_detection'
SERVICE_DISABLE_MOTION = 'disable_motion_detection'
SERVICE_SNAPSHOT = 'snapshot'

SCAN_INTERVAL = timedelta(seconds=30)
ENTITY_ID_FORMAT = DOMAIN + '.{}'

ATTR_FILENAME = 'filename'

STATE_RECORDING = 'recording'
STATE_STREAMING = 'streaming'
STATE_IDLE = 'idle'

# Bitfield of features supported by the camera entity
SUPPORT_ON_OFF = 1

DEFAULT_CONTENT_TYPE = 'image/jpeg'
ENTITY_IMAGE_URL = '/api/camera_proxy/{0}?token={1}'

TOKEN_CHANGE_INTERVAL = timedelta(minutes=5)
_RND = SystemRandom()

FALLBACK_STREAM_INTERVAL = 1  # seconds
MIN_STREAM_INTERVAL = 0.5  # seconds

CAMERA_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

CAMERA_SERVICE_SNAPSHOT = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_FILENAME): cv.template
})

WS_TYPE_CAMERA_THUMBNAIL = 'camera_thumbnail'
SCHEMA_WS_CAMERA_THUMBNAIL = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_CAMERA_THUMBNAIL,
    vol.Required('entity_id'): cv.entity_id
})


@attr.s
class Image:
    """Represent an image."""

    content_type = attr.ib(type=str)
    content = attr.ib(type=bytes)


@bind_hass
def turn_off(hass, entity_id=None):
    """Turn off camera."""
    hass.add_job(async_turn_off, hass, entity_id)


@bind_hass
async def async_turn_off(hass, entity_id=None):
    """Turn off camera."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data)


@bind_hass
def turn_on(hass, entity_id=None):
    """Turn on camera."""
    hass.add_job(async_turn_on, hass, entity_id)


@bind_hass
async def async_turn_on(hass, entity_id=None):
    """Turn on camera, and set operation mode."""
    data = {}
    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
def enable_motion_detection(hass, entity_id=None):
    """Enable Motion Detection."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_ENABLE_MOTION, data))


@bind_hass
def disable_motion_detection(hass, entity_id=None):
    """Disable Motion Detection."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_DISABLE_MOTION, data))


@bind_hass
@callback
def async_snapshot(hass, filename, entity_id=None):
    """Make a snapshot from a camera."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_FILENAME] = filename

    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_SNAPSHOT, data))


@bind_hass
async def async_get_image(hass, entity_id, timeout=10):
    """Fetch an image from a camera entity."""
    component = hass.data.get(DOMAIN)

    if component is None:
        raise HomeAssistantError('Camera component not setup')

    camera = component.get_entity(entity_id)

    if camera is None:
        raise HomeAssistantError('Camera not found')

    if not camera.is_on:
        raise HomeAssistantError('Camera is off')

    with suppress(asyncio.CancelledError, asyncio.TimeoutError):
        with async_timeout.timeout(timeout, loop=hass.loop):
            image = await camera.async_camera_image()

            if image:
                return Image(camera.content_type, image)

    raise HomeAssistantError('Unable to get image')


async def async_setup(hass, config):
    """Set up the camera component."""
    component = hass.data[DOMAIN] = \
        EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    hass.http.register_view(CameraImageView(component))
    hass.http.register_view(CameraMjpegStream(component))
    hass.components.websocket_api.async_register_command(
        WS_TYPE_CAMERA_THUMBNAIL, websocket_camera_thumbnail,
        SCHEMA_WS_CAMERA_THUMBNAIL
    )

    await component.async_setup(config)

    @callback
    def update_tokens(time):
        """Update tokens of the entities."""
        for entity in component.entities:
            entity.async_update_token()
            hass.async_add_job(entity.async_update_ha_state())

    hass.helpers.event.async_track_time_interval(
        update_tokens, TOKEN_CHANGE_INTERVAL)

    async def async_handle_camera_service(service):
        """Handle calls to the camera services."""
        target_cameras = component.async_extract_from_service(service)

        update_tasks = []
        for camera in target_cameras:
            if service.service == SERVICE_ENABLE_MOTION:
                await camera.async_enable_motion_detection()
            elif service.service == SERVICE_DISABLE_MOTION:
                await camera.async_disable_motion_detection()
            elif service.service == SERVICE_TURN_OFF and \
                    camera.supported_features & SUPPORT_ON_OFF:
                await camera.async_turn_off()
            elif service.service == SERVICE_TURN_ON and \
                    camera.supported_features & SUPPORT_ON_OFF:
                await camera.async_turn_on()

            if not camera.should_poll:
                continue
            update_tasks.append(camera.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks, loop=hass.loop)

    async def async_handle_snapshot_service(service):
        """Handle snapshot services calls."""
        target_cameras = component.async_extract_from_service(service)
        filename = service.data[ATTR_FILENAME]
        filename.hass = hass

        for camera in target_cameras:
            snapshot_file = filename.async_render(
                variables={ATTR_ENTITY_ID: camera})

            # check if we allow to access to that file
            if not hass.config.is_allowed_path(snapshot_file):
                _LOGGER.error(
                    "Can't write %s, no access to path!", snapshot_file)
                continue

            image = await camera.async_camera_image()

            def _write_image(to_file, image_data):
                """Executor helper to write image."""
                with open(to_file, 'wb') as img_file:
                    img_file.write(image_data)

            try:
                await hass.async_add_job(
                    _write_image, snapshot_file, image)
            except OSError as err:
                _LOGGER.error("Can't write image to file: %s", err)

    hass.services.async_register(
        DOMAIN, SERVICE_TURN_OFF, async_handle_camera_service,
        schema=CAMERA_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, async_handle_camera_service,
        schema=CAMERA_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE_MOTION, async_handle_camera_service,
        schema=CAMERA_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE_MOTION, async_handle_camera_service,
        schema=CAMERA_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SNAPSHOT, async_handle_snapshot_service,
        schema=CAMERA_SERVICE_SNAPSHOT)

    return True


async def async_setup_entry(hass, entry):
    """Setup a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class Camera(Entity):
    """The base class for camera entities."""

    def __init__(self):
        """Initialize a camera."""
        self.is_streaming = False
        self.content_type = DEFAULT_CONTENT_TYPE
        self.access_tokens = collections.deque([], 2)
        self.async_update_token()

    @property
    def should_poll(self):
        """No need to poll cameras."""
        return False

    @property
    def entity_picture(self):
        """Return a link to the camera feed as entity picture."""
        return ENTITY_IMAGE_URL.format(self.entity_id, self.access_tokens[-1])

    @property
    def supported_features(self):
        """Flag supported features."""
        return 0

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return False

    @property
    def brand(self):
        """Return the camera brand."""
        return None

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return None

    @property
    def model(self):
        """Return the camera model."""
        return None

    @property
    def frame_interval(self):
        """Return the interval between frames of the mjpeg stream."""
        return 0.5

    def camera_image(self):
        """Return bytes of camera image."""
        raise NotImplementedError()

    @callback
    def async_camera_image(self):
        """Return bytes of camera image.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.camera_image)

    async def handle_async_still_stream(self, request, interval):
        """Generate an HTTP MJPEG stream from camera images.

        This method must be run in the event loop.
        """
        response = web.StreamResponse()
        response.content_type = ('multipart/x-mixed-replace; '
                                 'boundary=--frameboundary')
        await response.prepare(request)

        async def write_to_mjpeg_stream(img_bytes):
            """Write image to stream."""
            await response.write(bytes(
                '--frameboundary\r\n'
                'Content-Type: {}\r\n'
                'Content-Length: {}\r\n\r\n'.format(
                    self.content_type, len(img_bytes)),
                'utf-8') + img_bytes + b'\r\n')

        last_image = None

        while True:
            img_bytes = await self.async_camera_image()
            if not img_bytes:
                break

            if img_bytes and img_bytes != last_image:
                await write_to_mjpeg_stream(img_bytes)

                # Chrome seems to always ignore first picture,
                # print it twice.
                if last_image is None:
                    await write_to_mjpeg_stream(img_bytes)
                last_image = img_bytes

            await asyncio.sleep(interval)

        return response

    async def handle_async_mjpeg_stream(self, request):
        """Serve an HTTP MJPEG stream from the camera.

        This method can be overridden by camera plaforms to proxy
        a direct stream from the camera.
        This method must be run in the event loop.
        """
        await self.handle_async_still_stream(request, self.frame_interval)

    @property
    def state(self):
        """Return the camera state."""
        if self.is_recording:
            return STATE_RECORDING
        if self.is_streaming:
            return STATE_STREAMING
        return STATE_IDLE

    @property
    def is_on(self):
        """Return true if on."""
        return True

    def turn_off(self):
        """Turn off camera."""
        raise NotImplementedError()

    @callback
    def async_turn_off(self):
        """Turn off camera."""
        return self.hass.async_add_job(self.turn_off)

    def turn_on(self):
        """Turn off camera."""
        raise NotImplementedError()

    @callback
    def async_turn_on(self):
        """Turn off camera."""
        return self.hass.async_add_job(self.turn_on)

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        raise NotImplementedError()

    @callback
    def async_enable_motion_detection(self):
        """Call the job and enable motion detection."""
        return self.hass.async_add_job(self.enable_motion_detection)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        raise NotImplementedError()

    @callback
    def async_disable_motion_detection(self):
        """Call the job and disable motion detection."""
        return self.hass.async_add_job(self.disable_motion_detection)

    @property
    def state_attributes(self):
        """Return the camera state attributes."""
        attrs = {
            'access_token': self.access_tokens[-1],
        }

        if self.model:
            attrs['model_name'] = self.model

        if self.brand:
            attrs['brand'] = self.brand

        if self.motion_detection_enabled:
            attrs['motion_detection'] = self.motion_detection_enabled

        return attrs

    @callback
    def async_update_token(self):
        """Update the used token."""
        self.access_tokens.append(
            hashlib.sha256(
                _RND.getrandbits(256).to_bytes(32, 'little')).hexdigest())


class CameraView(HomeAssistantView):
    """Base CameraView."""

    requires_auth = False

    def __init__(self, component):
        """Initialize a basic camera view."""
        self.component = component

    async def get(self, request, entity_id):
        """Start a GET request."""
        camera = self.component.get_entity(entity_id)

        if camera is None:
            raise web.HTTPNotFound()

        authenticated = (request[KEY_AUTHENTICATED] or
                         request.query.get('token') in camera.access_tokens)

        if not authenticated:
            raise web.HTTPUnauthorized()

        if not camera.is_on:
            _LOGGER.debug('Camera is off.')
            raise web.HTTPServiceUnavailable()

        return await self.handle(request, camera)

    async def handle(self, request, camera):
        """Handle the camera request."""
        raise NotImplementedError()


class CameraImageView(CameraView):
    """Camera view to serve an image."""

    url = '/api/camera_proxy/{entity_id}'
    name = 'api:camera:image'

    async def handle(self, request, camera):
        """Serve camera image."""
        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            with async_timeout.timeout(10, loop=request.app['hass'].loop):
                image = await camera.async_camera_image()

            if image:
                return web.Response(body=image,
                                    content_type=camera.content_type)

        raise web.HTTPInternalServerError()


class CameraMjpegStream(CameraView):
    """Camera View to serve an MJPEG stream."""

    url = '/api/camera_proxy_stream/{entity_id}'
    name = 'api:camera:stream'

    async def handle(self, request, camera):
        """Serve camera stream, possibly with interval."""
        interval = request.query.get('interval')
        if interval is None:
            return await camera.handle_async_mjpeg_stream(request)

        try:
            # Compose camera stream from stills
            interval = float(request.query.get('interval'))
            if interval < MIN_STREAM_INTERVAL:
                raise ValueError("Stream interval must be be > {}"
                                 .format(MIN_STREAM_INTERVAL))
            return await camera.handle_async_still_stream(request, interval)
        except ValueError:
            raise web.HTTPBadRequest()


@callback
def websocket_camera_thumbnail(hass, connection, msg):
    """Handle get camera thumbnail websocket command.

    Async friendly.
    """
    async def send_camera_still():
        """Send a camera still."""
        try:
            image = await async_get_image(hass, msg['entity_id'])
            connection.send_message_outside(websocket_api.result_message(
                msg['id'], {
                    'content_type': image.content_type,
                    'content': base64.b64encode(image.content).decode('utf-8')
                }
            ))
        except HomeAssistantError:
            connection.send_message_outside(websocket_api.error_message(
                msg['id'], 'image_fetch_failed', 'Unable to fetch image'))

    hass.async_add_job(send_camera_still())
