"""
Support for Synology Surveillance Station Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.synology/
"""
import asyncio
import logging

import voluptuous as vol

import aiohttp
import async_timeout

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
    CONF_URL, CONF_WHITELIST, CONF_VERIFY_SSL)
from homeassistant.components.camera import (
    Camera, PLATFORM_SCHEMA)
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession, async_create_clientsession,
    async_aiohttp_proxy_stream)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.async import run_coroutine_threadsafe

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Synology Camera'
DEFAULT_STREAM_ID = '0'
TIMEOUT = 5
CONF_CAMERA_NAME = 'camera_name'
CONF_STREAM_ID = 'stream_id'

QUERY_CGI = 'query.cgi'
QUERY_API = 'SYNO.API.Info'
AUTH_API = 'SYNO.API.Auth'
CAMERA_API = 'SYNO.SurveillanceStation.Camera'
STREAMING_API = 'SYNO.SurveillanceStation.VideoStream'
SESSION_ID = '0'

WEBAPI_PATH = '/webapi/'
AUTH_PATH = 'auth.cgi'
CAMERA_PATH = 'camera.cgi'
STREAMING_PATH = 'SurveillanceStation/videoStreaming.cgi'
CONTENT_TYPE_HEADER = 'Content-Type'

SYNO_API_URL = '{0}{1}{2}'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_WHITELIST, default=[]): cv.ensure_list,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup a Synology IP Camera."""
    verify_ssl = config.get(CONF_VERIFY_SSL)
    websession_init = async_get_clientsession(hass, verify_ssl)

    # Determine API to use for authentication
    syno_api_url = SYNO_API_URL.format(
        config.get(CONF_URL), WEBAPI_PATH, QUERY_CGI)

    query_payload = {
        'api': QUERY_API,
        'method': 'Query',
        'version': '1',
        'query': 'SYNO.'
    }
    query_req = None
    try:
        with async_timeout.timeout(TIMEOUT, loop=hass.loop):
            query_req = yield from websession_init.get(
                syno_api_url,
                params=query_payload
            )

        query_resp = yield from query_req.json()
        auth_path = query_resp['data'][AUTH_API]['path']
        camera_api = query_resp['data'][CAMERA_API]['path']
        camera_path = query_resp['data'][CAMERA_API]['path']
        streaming_path = query_resp['data'][STREAMING_API]['path']

    except (asyncio.TimeoutError, aiohttp.errors.ClientError):
        _LOGGER.exception("Error on %s", syno_api_url)
        return False

    finally:
        if query_req is not None:
            yield from query_req.release()

    # Authticate to NAS to get a session id
    syno_auth_url = SYNO_API_URL.format(
        config.get(CONF_URL), WEBAPI_PATH, auth_path)

    session_id = yield from get_session_id(
        hass,
        websession_init,
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        syno_auth_url
    )

    # init websession
    websession = async_create_clientsession(
        hass, verify_ssl, cookies={'id': session_id})

    # Use SessionID to get cameras in system
    syno_camera_url = SYNO_API_URL.format(
        config.get(CONF_URL), WEBAPI_PATH, camera_api)

    camera_payload = {
        'api': CAMERA_API,
        'method': 'List',
        'version': '1'
    }
    try:
        with async_timeout.timeout(TIMEOUT, loop=hass.loop):
            camera_req = yield from websession.get(
                syno_camera_url,
                params=camera_payload
            )
    except (asyncio.TimeoutError, aiohttp.errors.ClientError):
        _LOGGER.exception("Error on %s", syno_camera_url)
        return False

    camera_resp = yield from camera_req.json()
    cameras = camera_resp['data']['cameras']
    yield from camera_req.release()

    # add cameras
    devices = []
    for camera in cameras:
        if not config.get(CONF_WHITELIST):
            camera_id = camera['id']
            snapshot_path = camera['snapshot_path']

            device = SynologyCamera(
                hass,
                websession,
                config,
                camera_id,
                camera['name'],
                snapshot_path,
                streaming_path,
                camera_path,
                auth_path
            )
            devices.append(device)

    async_add_devices(devices)


@asyncio.coroutine
def get_session_id(hass, websession, username, password, login_url):
    """Get a session id."""
    auth_payload = {
        'api': AUTH_API,
        'method': 'Login',
        'version': '2',
        'account': username,
        'passwd': password,
        'session': 'SurveillanceStation',
        'format': 'sid'
    }
    auth_req = None
    try:
        with async_timeout.timeout(TIMEOUT, loop=hass.loop):
            auth_req = yield from websession.get(
                login_url,
                params=auth_payload
            )
        auth_resp = yield from auth_req.json()
        return auth_resp['data']['sid']

    except (asyncio.TimeoutError, aiohttp.errors.ClientError):
        _LOGGER.exception("Error on %s", login_url)
        return False

    finally:
        if auth_req is not None:
            yield from auth_req.release()


class SynologyCamera(Camera):
    """An implementation of a Synology NAS based IP camera."""

    def __init__(self, hass, websession, config, camera_id,
                 camera_name, snapshot_path, streaming_path, camera_path,
                 auth_path):
        """Initialize a Synology Surveillance Station camera."""
        super().__init__()
        self.hass = hass
        self._websession = websession
        self._name = camera_name
        self._synology_url = config.get(CONF_URL)
        self._camera_name = config.get(CONF_CAMERA_NAME)
        self._stream_id = config.get(CONF_STREAM_ID)
        self._camera_id = camera_id
        self._snapshot_path = snapshot_path
        self._streaming_path = streaming_path
        self._camera_path = camera_path
        self._auth_path = auth_path

    def camera_image(self):
        """Return bytes of camera image."""
        return run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop).result()

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        image_url = SYNO_API_URL.format(
            self._synology_url, WEBAPI_PATH, self._camera_path)

        image_payload = {
            'api': CAMERA_API,
            'method': 'GetSnapshot',
            'version': '1',
            'cameraId': self._camera_id
        }
        try:
            with async_timeout.timeout(TIMEOUT, loop=self.hass.loop):
                response = yield from self._websession.get(
                    image_url,
                    params=image_payload
                )
        except (asyncio.TimeoutError, aiohttp.errors.ClientError):
            _LOGGER.exception("Error on %s", image_url)
            return None

        image = yield from response.read()
        yield from response.release()

        return image

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Return a MJPEG stream image response directly from the camera."""
        streaming_url = SYNO_API_URL.format(
            self._synology_url, WEBAPI_PATH, self._streaming_path)

        streaming_payload = {
            'api': STREAMING_API,
            'method': 'Stream',
            'version': '1',
            'cameraId': self._camera_id,
            'format': 'mjpeg'
        }
        stream_coro = self._websession.get(
            streaming_url, params=streaming_payload)

        yield from async_aiohttp_proxy_stream(self.hass, request, stream_coro)

    @property
    def name(self):
        """Return the name of this device."""
        return self._name
