# pylint: disable=too-many-lines
"""
Component to interface with cameras.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/camera/
"""
import asyncio
import collections
from contextlib import suppress
from datetime import timedelta
import logging
import hashlib
from random import SystemRandom

import aiohttp
from aiohttp import web
import async_timeout
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (ATTR_ENTITY_ID, ATTR_ENTITY_PICTURE)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import bind_hass
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.components.http import HomeAssistantView, KEY_AUTHENTICATED
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

DEFAULT_CONTENT_TYPE = 'image/jpeg'
ENTITY_IMAGE_URL = '/api/camera_proxy/{0}?token={1}'

TOKEN_CHANGE_INTERVAL = timedelta(minutes=5)
_RND = SystemRandom()

CAMERA_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

CAMERA_SERVICE_SNAPSHOT = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_FILENAME): cv.template
})


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
def async_snapshot(hass, filename, entity_id=None):
    """Make a snapshot from a camera."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_FILENAME] = filename

    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_SNAPSHOT, data))


@bind_hass
@asyncio.coroutine
def async_get_image(hass, entity_id, timeout=10):
    """Fetch a image from a camera entity."""
    websession = async_get_clientsession(hass)
    state = hass.states.get(entity_id)

    if state is None:
        raise HomeAssistantError(
            "No entity '{0}' for grab a image".format(entity_id))

    url = "{0}{1}".format(
        hass.config.api.base_url,
        state.attributes.get(ATTR_ENTITY_PICTURE)
    )

    try:
        with async_timeout.timeout(timeout, loop=hass.loop):
            response = yield from websession.get(url)

            if response.status != 200:
                raise HomeAssistantError("Error {0} on {1}".format(
                    response.status, url))

            image = yield from response.read()
            return image

    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise HomeAssistantError("Can't connect to {0}".format(url))


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the camera component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    hass.http.register_view(CameraImageView(component))
    hass.http.register_view(CameraMjpegStream(component))

    yield from component.async_setup(config)

    @callback
    def update_tokens(time):
        """Update tokens of the entities."""
        for entity in component.entities:
            entity.async_update_token()
            hass.async_add_job(entity.async_update_ha_state())

    hass.helpers.event.async_track_time_interval(
        update_tokens, TOKEN_CHANGE_INTERVAL)

    @asyncio.coroutine
    def async_handle_camera_service(service):
        """Handle calls to the camera services."""
        target_cameras = component.async_extract_from_service(service)

        update_tasks = []
        for camera in target_cameras:
            if service.service == SERVICE_ENABLE_MOTION:
                yield from camera.async_enable_motion_detection()
            elif service.service == SERVICE_DISABLE_MOTION:
                yield from camera.async_disable_motion_detection()

            if not camera.should_poll:
                continue
            update_tasks.append(camera.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    @asyncio.coroutine
    def async_handle_snapshot_service(service):
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

            image = yield from camera.async_camera_image()

            def _write_image(to_file, image_data):
                """Executor helper to write image."""
                with open(to_file, 'wb') as img_file:
                    img_file.write(image_data)

            try:
                yield from hass.async_add_job(
                    _write_image, snapshot_file, image)
            except OSError as err:
                _LOGGER.error("Can't write image to file: %s", err)

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

    def camera_image(self):
        """Return bytes of camera image."""
        raise NotImplementedError()

    def async_camera_image(self):
        """Return bytes of camera image.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.camera_image)

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from camera images.

        This method must be run in the event loop.
        """
        response = web.StreamResponse()

        response.content_type = ('multipart/x-mixed-replace; '
                                 'boundary=--frameboundary')
        yield from response.prepare(request)

        def write(img_bytes):
            """Write image to stream."""
            response.write(bytes(
                '--frameboundary\r\n'
                'Content-Type: {}\r\n'
                'Content-Length: {}\r\n\r\n'.format(
                    self.content_type, len(img_bytes)),
                'utf-8') + img_bytes + b'\r\n')

        last_image = None

        try:
            while True:
                img_bytes = yield from self.async_camera_image()
                if not img_bytes:
                    break

                if img_bytes and img_bytes != last_image:
                    write(img_bytes)

                    # Chrome seems to always ignore first picture,
                    # print it twice.
                    if last_image is None:
                        write(img_bytes)

                    last_image = img_bytes
                    yield from response.drain()

                yield from asyncio.sleep(.5)

        except asyncio.CancelledError:
            _LOGGER.debug("Stream closed by frontend.")
            response = None

        finally:
            if response is not None:
                yield from response.write_eof()

    @property
    def state(self):
        """Return the camera state."""
        if self.is_recording:
            return STATE_RECORDING
        elif self.is_streaming:
            return STATE_STREAMING
        return STATE_IDLE

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        raise NotImplementedError()

    def async_enable_motion_detection(self):
        """Call the job and enable motion detection."""
        return self.hass.async_add_job(self.enable_motion_detection)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        raise NotImplementedError()

    def async_disable_motion_detection(self):
        """Call the job and disable motion detection."""
        return self.hass.async_add_job(self.disable_motion_detection)

    @property
    def state_attributes(self):
        """Return the camera state attributes."""
        attr = {
            'access_token': self.access_tokens[-1],
        }

        if self.model:
            attr['model_name'] = self.model

        if self.brand:
            attr['brand'] = self.brand

        if self.motion_detection_enabled:
            attr['motion_detection'] = self.motion_detection_enabled

        return attr

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

    @asyncio.coroutine
    def get(self, request, entity_id):
        """Start a GET request."""
        camera = self.component.get_entity(entity_id)

        if camera is None:
            status = 404 if request[KEY_AUTHENTICATED] else 401
            return web.Response(status=status)

        authenticated = (request[KEY_AUTHENTICATED] or
                         request.query.get('token') in camera.access_tokens)

        if not authenticated:
            return web.Response(status=401)

        response = yield from self.handle(request, camera)
        return response

    @asyncio.coroutine
    def handle(self, request, camera):
        """Handle the camera request."""
        raise NotImplementedError()


class CameraImageView(CameraView):
    """Camera view to serve an image."""

    url = '/api/camera_proxy/{entity_id}'
    name = 'api:camera:image'

    @asyncio.coroutine
    def handle(self, request, camera):
        """Serve camera image."""
        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            with async_timeout.timeout(10, loop=request.app['hass'].loop):
                image = yield from camera.async_camera_image()

            if image:
                return web.Response(body=image,
                                    content_type=camera.content_type)

        return web.Response(status=500)


class CameraMjpegStream(CameraView):
    """Camera View to serve an MJPEG stream."""

    url = '/api/camera_proxy_stream/{entity_id}'
    name = 'api:camera:stream'

    @asyncio.coroutine
    def handle(self, request, camera):
        """Serve camera image."""
        yield from camera.handle_async_mjpeg_stream(request)
