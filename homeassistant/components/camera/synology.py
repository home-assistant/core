"""
Support for Synology Surveillance Station Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.synology/
"""
import asyncio
import json
import logging
import urllib

import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
    CONF_URL, CONF_WHITELIST, CONF_VERIFY_SSL, CONF_TIMEOUT)
from homeassistant.components.camera import (
    Camera, PLATFORM_SCHEMA)
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_aiohttp_proxy_web)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.async import run_coroutine_threadsafe

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Synology Camera'
DEFAULT_TIMEOUT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_WHITELIST, default=[]): cv.ensure_list,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a Synology IP Camera."""
    verify_ssl = config.get(CONF_VERIFY_SSL)
    timeout = config.get(CONF_TIMEOUT)

    try:
        surveillance = SurveillanceStation(
            config.get(CONF_URL),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            verify_ssl=verify_ssl,
            timeout=timeout
        )
    except (requests.exceptions.RequestException, ValueError):
        _LOGGER.exception("Error when initializing SurveillanceStation")
        return False

    cameras = surveillance.get_all_cameras()
    websession = async_create_clientsession(hass, verify_ssl)

    # add cameras
    devices = []
    for camera in cameras:
        if not config.get(CONF_WHITELIST):
            device = SynologyCamera(hass, websession, surveillance,
                                    camera.camera_id)
            devices.append(device)

    async_add_devices(devices)


class SynologyCamera(Camera):
    """An implementation of a Synology NAS based IP camera."""

    def __init__(self, hass, websession, surveillance, camera_id):
        """Initialize a Synology Surveillance Station camera."""
        super().__init__()
        self.hass = hass
        self._websession = websession
        self._surveillance = surveillance
        self._camera_id = camera_id
        self._camera = self._surveillance.get_camera(camera_id)
        self._motion_setting = self._surveillance.get_motion_setting(camera_id)
        self.is_streaming = self._camera.is_enabled

    def camera_image(self):
        """Return bytes of camera image."""
        return run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop).result()

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        return self._surveillance.get_camera_image(self._camera_id)

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Return a MJPEG stream image response directly from the camera."""
        streaming_url = self._camera.video_stream_url
        stream_coro = self._websession.get(streaming_url)

        yield from async_aiohttp_proxy_web(self.hass, request, stream_coro)

    @property
    def name(self):
        """Return the name of this device."""
        return self._camera.name

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._camera.is_recording

    def should_poll(self):
        """Update the recording state periodically."""
        return True

    @asyncio.coroutine
    def async_update(self):
        """Update the status of the camera."""
        self._surveillance.update()
        self._camera = self._surveillance.get_camera(self._camera.camera_id)
        self._motion_setting = self._surveillance.get_motion_setting(
            self._camera.camera_id)
        self.is_streaming = self._camera.is_enabled

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._motion_setting.is_enabled

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        self._surveillance.enable_motion_detection(self._camera_id)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self._surveillance.disable_motion_detection(self._camera_id)


BASE_API_INFO = {
    'auth': {
        'name': 'SYNO.API.Auth',
        'version': 2
    },
    'camera': {
        'name': 'SYNO.SurveillanceStation.Camera',
        'version': 1
    },
    'camera_event': {
        'name': 'SYNO.SurveillanceStation.Camera.Event',
        'version': 1
    },
    'video_stream': {
        'name': 'SYNO.SurveillanceStation.VideoStream',
        'version': 1
    },
}

API_NAMES = map(lambda api: api['name'], BASE_API_INFO.values())

RECORDING_STATUS = [
    # Continue recording schedule
    1,
    # Motion detect recording schedule
    2,
    # Digital input recording schedule
    3,
    # Digital input recording schedule
    4,
    # Manual recording schedule
    5]
MOTION_DETECTION_SOURCE_DISABLED = -1
MOTION_DETECTION_SOURCE_BY_CAMERA = 0
MOTION_DETECTION_SOURCE_BY_SURVEILLANCE = 1


class Api:
    """An implementation of a Synology SurveillanceStation API."""

    def __init__(self, url, username, password, timeout=10, verify_ssl=True):
        """Initialize a Synology Surveillance API."""
        self._base_url = url + '/webapi/'
        self._username = username
        self._password = password
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._api_info = None
        self._sid = None

        self._initialize_api_info()
        self._initialize_api_sid()

    def _initialize_api_info(self, **kwargs):
        content = self._get_json(self._base_url + 'query.cgi', {
            'api': 'SYNO.API.Info',
            'method': 'Query',
            'version': '1',
            'query': ','.join(API_NAMES),
            **kwargs
        })

        self._api_info = BASE_API_INFO
        for api in self._api_info.values():
            api_name = api['name']
            api['url'] = self._base_url + content['data'][api_name]['path']

    def _initialize_api_sid(self, **kwargs):
        api = self._api_info['auth']
        content = self._get_json(api['url'], {
            'api': api['name'],
            'method': 'Login',
            'version': api['version'],
            'account': self._username,
            'passwd': self._password,
            'format': 'sid',
            **kwargs
        })

        self._sid = content['data']['sid']

    def camera_list(self, **kwargs):
        """Return a list of cameras."""
        api = self._api_info['camera']
        content = self._get_json(api['url'], {
            '_sid': self._sid,
            'api': api['name'],
            'method': 'List',
            'version': api['version'],
            **kwargs
        })

        cameras = []

        for data in content['data']['cameras']:
            cameras.append(Camera(data, self._video_stream_url))

        return cameras

    def camera_info(self, camera_ids, **kwargs):
        """Return a list of cameras matching camera_ids."""
        api = self._api_info['camera']
        content = self._get_json(api['url'], {
            '_sid': self._sid,
            'api': api['name'],
            'method': 'GetInfo',
            'version': api['version'],
            'cameraIds': ', '.join(str(id) for id in camera_ids),
            **kwargs
        })

        cameras = []

        for data in content['data']['cameras']:
            cameras.append(Camera(data, self._video_stream_url))

        return cameras

    def camera_snapshot(self, camera_id, **kwargs):
        """Return bytes of camera image."""
        api = self._api_info['camera']
        response = self._get(api['url'], {
            '_sid': self._sid,
            'api': api['name'],
            'method': 'GetSnapshot',
            'version': api['version'],
            'cameraId': camera_id,
            **kwargs
        })

        return response.content

    def camera_event_motion_enum(self, camera_id, **kwargs):
        """Return motion settings matching camera_id."""
        api = self._api_info['camera_event']
        content = self._get_json(api['url'], {
            '_sid': self._sid,
            'api': api['name'],
            'method': 'MotionEnum',
            'version': api['version'],
            'camId': camera_id,
            **kwargs
        })

        return MotionSetting(camera_id, content['data']['MDParam'])

    def camera_event_md_param_save(self, camera_id, **kwargs):
        """Update motion settings matching camera_id with keyword args."""
        api = self._api_info['camera_event']
        content = self._get_json(api['url'], {
            '_sid': self._sid,
            'api': api['name'],
            'method': 'MDParamSave',
            'version': api['version'],
            'camId': camera_id,
            **kwargs
        })

        return content['data']['camId']

    def _video_stream_url(self, camera_id, video_format='mjpeg'):
        api = self._api_info['video_stream']

        return api['url'] + '?' + urllib.parse.urlencode({
            '_sid': self._sid,
            'api': api['name'],
            'method': 'Stream',
            'version': api['version'],
            'cameraId': camera_id,
            'format': video_format,
        })

    def _get(self, url, payload):
        response = requests.get(url, payload, timeout=self._timeout,
                                verify=self._verify_ssl)

        if response.status_code == 200:
            return response
        else:
            response.raise_for_status()

    def _get_json(self, url, payload):
        response = self._get(url, payload)
        content = json.loads(response.content)

        if 'success' not in content or content['success'] is False:
            raise ValueError('Invalid or failed response', content)

        return content


class Camera:
    """An representation of a Synology SurveillanceStation camera."""

    def __init__(self, data, video_stream_url_provider):
        """Initialize a Surveillance Station camera."""
        self._camera_id = data['id']
        self._name = data['name']
        self._is_enabled = data['enabled']
        self._recording_status = data['recStatus']
        self._video_stream_url = video_stream_url_provider(self.camera_id)

    @property
    def camera_id(self):
        """Return id of the camera."""
        return self._camera_id

    @property
    def name(self):
        """Return name of the camera."""
        return self._name

    @property
    def video_stream_url(self):
        """Return video stream url of the camera."""
        return self._video_stream_url

    @property
    def is_enabled(self):
        """Return true if camera is enabled."""
        return self._is_enabled

    @property
    def is_recording(self):
        """Return true if camera is recording."""
        return self._recording_status in RECORDING_STATUS


class MotionSetting:
    """An representation of a Synology SurveillanceStation motion setting."""

    def __init__(self, camera_id, data):
        """Initialize a Surveillance Station motion setting."""
        self._camera_id = camera_id
        self._source = data['source']

    @property
    def camera_id(self):
        """Return id of the camera."""
        return self._camera_id

    @property
    def is_enabled(self):
        """Return true if motion detection is enabled."""
        return MOTION_DETECTION_SOURCE_DISABLED != self._source


class SurveillanceStation:
    """An implementation of a Synology SurveillanceStation."""

    def __init__(self, url, username, password, timeout=10, verify_ssl=True):
        """Initialize a Surveillance Station."""
        self._api = Api(url, username, password, timeout, verify_ssl)
        self._cameras_by_id = None
        self._motion_settings_by_id = None

        self.update()

    def update(self):
        """Update cameras and motion settings with latest from API."""
        cameras = self._api.camera_list()
        self._cameras_by_id = {v.camera_id: v for i, v in enumerate(cameras)}

        motion_settings = []
        for camera_id in self._cameras_by_id.keys():
            motion_setting = self._api.camera_event_motion_enum(camera_id)
            motion_settings.append(motion_setting)

        self._motion_settings_by_id = {
            v.camera_id: v for i, v in enumerate(motion_settings)}

    def get_all_cameras(self):
        """Return a list of cameras."""
        return self._cameras_by_id.values()

    def get_camera(self, camera_id):
        """Return camera matching camera_id."""
        return self._cameras_by_id[camera_id]

    def get_camera_image(self, camera_id):
        """Return bytes of camera image for camera matching camera_id."""
        return self._api.camera_snapshot(camera_id)

    def get_motion_setting(self, camera_id):
        """Return motion setting matching camera_id."""
        return self._motion_settings_by_id[camera_id]

    def enable_motion_detection(self, camera_id):
        """Enable motion detection for camera matching camera_id."""
        self._api.camera_event_md_param_save(
            camera_id,
            source=MOTION_DETECTION_SOURCE_BY_SURVEILLANCE)

    def disable_motion_detection(self, camera_id):
        """Disable motion detection for camera matching camera_id."""
        self._api.camera_event_md_param_save(
            camera_id,
            source=MOTION_DETECTION_SOURCE_DISABLED)
