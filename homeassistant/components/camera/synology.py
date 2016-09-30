"""
Support for IP Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.generic/
"""
import logging

from json import loads

import requests
from requests.auth import HTTPBasicAuth

from homeassistant.components.camera import DOMAIN, Camera
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup a Synology IP Camera."""
    if not validate_config({DOMAIN: config}, {DOMAIN: ['synology_url', 'username', 'password', 'camera_name']},
                           _LOGGER):
        return None

    add_devices_callback([SynologyCamera(config)])

# pylint: disable=too-many-instance-attributes
class SynologyCamera(Camera):
    """An implementation of a Synology NAS based IP camera."""

    def __init__(self, device_info):
        """Initialize a Synology Surveillance Station camera."""
        super().__init__()
        self._name = device_info.get('name', 'Synology Camera')
        self._username = device_info.get('username')
        self._password = device_info.get('password')
        self._synology_url = device_info['synology_url']
        self._camera_name = device_info['camera_name']
        self._stream_id = device_info['stream_id']

        """We need to get a session id to retrieve the still image path and the images themselves"""
        login_url = self._synology_url + '/webapi/auth.cgi?api=SYNO.API.Auth&method=Login&version=2&account=' + self._username + '&passwd=' + self._password + '&session=SurveillanceStation&format=sid'
        r1 = requests.get(login_url, verify=False)
        sidResp = loads(r1.text)
        sids = sidResp['data']
        self._sid = sids['sid']

        """With our session id (sid) we can get the snapshot path from the disk station. """
        url = self._synology_url + '/webapi/entry.cgi?api=SYNO.SurveillanceStation.Camera&method=List&version=1'
        r = requests.get(url, verify=False, cookies={'id': self._sid})
        camerasResp = loads(r.text)
        cameras = camerasResp['data']['cameras']

        for camera in cameras:
            if camera['name'] == self._camera_name:
                snapshot_path = camera['snapshot_path']
                self._camID = str(camera['id'])
                self._still_image_url = self._synology_url + snapshot_path
                self._mjpeg_url= self._synology_url + 'webapi/SurveillanceStation/streaming.cgi?api=SYNO.SurveillanceStation.Streaming&method=LiveStream&version=1&cameraId=' + self._camID

    def get_sid(self):
        """We need to get a session id to retrieve the still image path and the images themselves"""
        login_url = self._synology_url + '/webapi/auth.cgi?api=SYNO.API.Auth&method=Login&version=2&account=' + self._username + '&passwd=' + self._password + '&session=SurveillanceStation&format=sid'
        r = requests.get(login_url, verify=False)
        sidResp = loads(r.text)
        sids = sidResp['data']
        self._sid = sids['sid']

    def camera_image(self):
        """Return a still image response from the camera."""
        """With our session id (sid) we can get the snapshot path from the disk station. """
        try:
            response = requests.get(self._still_image_url,timeout=10, verify=False, cookies={'id': self._sid})
        except requests.exceptions.RequestException as error:
                _LOGGER.error('Error getting camera image: %s', error)
                return None
        return response.content

    def camera_stream(self):
        """Return a MJPEG stream image response directly from the camera."""
        resp = requests.get(self._mjpeg_url, stream=True, timeout=10, cookies={'id': self._sid})
        if loads(resp.text)['success'] == 'false':
            _LOGGER.error('Session ID %s expired for Synology NAS, getting new one', self._sid)
            self.get_sid()
            return requests.get(self._mjpeg_url, stream=True, timeout=10, cookies={'id': self._sid})
        else:
            return resp

    def mjpeg_steam(self, response):
        """Generate an HTTP MJPEG Stream from the Synology NAS."""
        stream = self.camera_stream()
        return response(
            stream.iter_content(chunk_size=1024),
            mimetype=stream.headers[CONTENT_TYPE_HEADER],
            direct_passthrough=True
        )

    @property
    def name(self):
        """Return the name of this device."""
        return self._name
