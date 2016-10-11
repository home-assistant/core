"""
Support for Synology Surveillance Station Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.synology/
"""
import logging

import voluptuous as vol

import requests

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
    CONF_URL, CONF_WHITELIST)
from homeassistant.components.camera import (
    Camera, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

#  pylint: disable=too-many-locals
DEFAULT_NAME = 'Synology Camera'
DEFAULT_STREAM_ID = '0'
TIMEOUT = 5
CONF_CAMERA_NAME = 'camera_name'
CONF_STREAM_ID = 'stream_id'
CONF_VALID_CERT = 'valid_cert'

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

SYNO_API_URL = '{0}{1}{2}'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_WHITELIST, default=[]): cv.ensure_list,
    vol.Optional(CONF_VALID_CERT, default=True): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a Synology IP Camera."""
    # Determine API to use for authentication
    syno_api_url = SYNO_API_URL.format(config.get(CONF_URL),
                                       WEBAPI_PATH,
                                       QUERY_CGI)
    query_payload = {'api': QUERY_API,
                     'method': 'Query',
                     'version': '1',
                     'query': 'SYNO.'}
    query_req = requests.get(syno_api_url,
                             params=query_payload,
                             verify=config.get(CONF_VALID_CERT),
                             timeout=TIMEOUT)
    query_resp = query_req.json()
    auth_path = query_resp['data'][AUTH_API]['path']
    camera_api = query_resp['data'][CAMERA_API]['path']
    camera_path = query_resp['data'][CAMERA_API]['path']
    streaming_path = query_resp['data'][STREAMING_API]['path']

    # Authticate to NAS to get a session id
    syno_auth_url = SYNO_API_URL.format(config.get(CONF_URL),
                                        WEBAPI_PATH,
                                        auth_path)
    session_id = get_session_id(config.get(CONF_USERNAME),
                                config.get(CONF_PASSWORD),
                                syno_auth_url,
                                config.get(CONF_VALID_CERT))

    # Use SessionID to get cameras in system
    syno_camera_url = SYNO_API_URL.format(config.get(CONF_URL),
                                          WEBAPI_PATH,
                                          camera_api)
    camera_payload = {'api': CAMERA_API,
                      'method': 'List',
                      'version': '1'}
    camera_req = requests.get(syno_camera_url,
                              params=camera_payload,
                              verify=config.get(CONF_VALID_CERT),
                              timeout=TIMEOUT,
                              cookies={'id': session_id})
    camera_resp = camera_req.json()
    cameras = camera_resp['data']['cameras']
    for camera in cameras:
        if not config.get(CONF_WHITELIST):
            camera_id = camera['id']
            snapshot_path = camera['snapshot_path']

            add_devices([SynologyCamera(config,
                                        camera_id,
                                        camera['name'],
                                        snapshot_path,
                                        streaming_path,
                                        camera_path,
                                        auth_path)])


def get_session_id(username, password, login_url, valid_cert):
    """Get a session id."""
    auth_payload = {'api': AUTH_API,
                    'method': 'Login',
                    'version': '2',
                    'account': username,
                    'passwd': password,
                    'session': 'SurveillanceStation',
                    'format': 'sid'}
    auth_req = requests.get(login_url,
                            params=auth_payload,
                            verify=valid_cert,
                            timeout=TIMEOUT)
    auth_resp = auth_req.json()
    return auth_resp['data']['sid']


# pylint: disable=too-many-instance-attributes
class SynologyCamera(Camera):
    """An implementation of a Synology NAS based IP camera."""

# pylint: disable=too-many-arguments
    def __init__(self, config, camera_id, camera_name,
                 snapshot_path, streaming_path, camera_path, auth_path):
        """Initialize a Synology Surveillance Station camera."""
        super().__init__()
        self._name = camera_name
        self._username = config.get(CONF_USERNAME)
        self._password = config.get(CONF_PASSWORD)
        self._synology_url = config.get(CONF_URL)
        self._api_url = config.get(CONF_URL) + 'webapi/'
        self._login_url = config.get(CONF_URL) + '/webapi/' + 'auth.cgi'
        self._camera_name = config.get(CONF_CAMERA_NAME)
        self._stream_id = config.get(CONF_STREAM_ID)
        self._valid_cert = config.get(CONF_VALID_CERT)
        self._camera_id = camera_id
        self._snapshot_path = snapshot_path
        self._streaming_path = streaming_path
        self._camera_path = camera_path
        self._auth_path = auth_path

        self._session_id = get_session_id(self._username,
                                          self._password,
                                          self._login_url,
                                          self._valid_cert)

    def get_sid(self):
        """Get a session id."""
        auth_payload = {'api': AUTH_API,
                        'method': 'Login',
                        'version': '2',
                        'account': self._username,
                        'passwd': self._password,
                        'session': 'SurveillanceStation',
                        'format': 'sid'}
        auth_req = requests.get(self._login_url,
                                params=auth_payload,
                                verify=self._valid_cert,
                                timeout=TIMEOUT)
        auth_resp = auth_req.json()
        self._session_id = auth_resp['data']['sid']

    def camera_image(self):
        """Return a still image response from the camera."""
        image_url = SYNO_API_URL.format(self._synology_url,
                                        WEBAPI_PATH,
                                        self._camera_path)
        image_payload = {'api': CAMERA_API,
                         'method': 'GetSnapshot',
                         'version': '1',
                         'cameraId': self._camera_id}
        try:
            response = requests.get(image_url,
                                    params=image_payload,
                                    timeout=TIMEOUT,
                                    verify=self._valid_cert,
                                    cookies={'id': self._session_id})
        except requests.exceptions.RequestException as error:
            _LOGGER.error('Error getting camera image: %s', error)
            return None

        return response.content

    def camera_stream(self):
        """Return a MJPEG stream image response directly from the camera."""
        streaming_url = SYNO_API_URL.format(self._synology_url,
                                            WEBAPI_PATH,
                                            self._streaming_path)
        streaming_payload = {'api': STREAMING_API,
                             'method': 'Stream',
                             'version': '1',
                             'cameraId': self._camera_id,
                             'format': 'mjpeg'}
        response = requests.get(streaming_url,
                                payload=streaming_payload,
                                stream=True,
                                timeout=TIMEOUT,
                                cookies={'id': self._session_id})
        return response

    def mjpeg_steam(self, response):
        """Generate an HTTP MJPEG Stream from the Synology NAS."""
        stream = self.camera_stream()
        return response(
            stream.iter_content(chunk_size=1024),
            mimetype=stream.headers['CONTENT_TYPE_HEADER'],
            direct_passthrough=True
        )

    @property
    def name(self):
        """Return the name of this device."""
        return self._name
