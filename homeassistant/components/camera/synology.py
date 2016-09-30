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
    CONF_URL, CONF_CAMERA_NAME, CONF_STREAM_ID)
from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Synology Camera'
DEFAULT_STREAM_ID = '0'
TIMEOUT = 10

# pylint: disable=line-too-long
MJPEG_URL = '{0}/webapi/SurveillanceStation/streaming.cgi?api=\
SYNO.SurveillanceStation.Streaming&method=LiveStream&version=1&cameraId={1}'
STILL_IMAGE_URL = '{0}{1}'
LOGIN_URL = '{0}/webapi/auth.cgi?api=SYNO.API.Auth&method=\
Login&version=2&account={1}&passwd={2}&session=SurveillanceStation&format=sid'
URL = '{0}/webapi/entry.cgi?\
api=SYNO.SurveillanceStation.Camera&method=List&version=1'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONF_CAMERA_NAME): cv.string,
    vol.Optional(CONF_STREAM_ID, default=DEFAULT_STREAM_ID): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a Synology IP Camera."""
    add_devices([SynologyCamera(config)])


# pylint: disable=too-many-instance-attributes
class SynologyCamera(Camera):
    """An implementation of a Synology NAS based IP camera."""

    def __init__(self, config):
        """Initialize a Synology Surveillance Station camera."""
        from json import loads
        super().__init__()
        self._name = config.get(CONF_NAME)
        self._username = config.get(CONF_USERNAME)
        self._password = config.get(CONF_PASSWORD)
        self._synology_url = config.get(CONF_URL)
        self._camera_name = config.get(CONF_CAMERA_NAME)
        self._stream_id = config.get(CONF_STREAM_ID)

        self.get_sid()

        # With our session id (sid) we can get the snapshot path.
        sidurl = URL.format(self._synology_url)
        req = requests.get(
            sidurl, timeout=TIMEOUT, verify=False, cookies={'id': self._sid})
        cam_resp = loads(req.text)
        cameras = cam_resp['data']['cameras']

        for camera in cameras:
            if camera['name'] == self._camera_name:
                snapshot_path = camera['snapshot_path']
                self._cam_id = str(camera['id'])
                self._still_image_url = STILL_IMAGE_URL.format(
                    self._synology_url, snapshot_path)
                self._mjpeg_url = MJPEG_URL.format(
                    self._synology_url, self._cam_id)

    def get_sid(self):
        """Get a session id."""
        from json import loads
        login_url = LOGIN_URL.format(
            self._synology_url, self._username, self._password)
        req = requests.get(login_url, timeout=TIMEOUT, verify=False)
        sid_resp = loads(req.text)
        sids = sid_resp['data']
        self._sid = sids['sid']

    def camera_image(self):
        """Return a still image response from the camera."""
        try:
            response = requests.get(
                self._still_image_url, timeout=TIMEOUT,
                verify=False, cookies={'id': self._sid})
        except requests.exceptions.RequestException as error:
            _LOGGER.error('Error getting camera image: %s', error)
            return None
        return response.content

    def camera_stream(self):
        """Return a MJPEG stream image response directly from the camera."""
        from json import loads
        resp = requests.get(
            self._mjpeg_url, stream=True, timeout=TIMEOUT,
            cookies={'id': self._sid})
        if loads(resp.text)['success'] == 'false':
            _LOGGER.error(
                'Session ID %s expired for NAS, getting new one', self._sid)
            self.get_sid()
            return requests.get(
                self._mjpeg_url, stream=True,
                timeout=TIMEOUT, cookies={'id': self._sid})
        else:
            return resp

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
