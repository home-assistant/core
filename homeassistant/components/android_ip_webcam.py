"""
Support for IP Webcam, an Android app that turns a device into a webcam.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/android_ip_webcam/
"""
import logging
from datetime import datetime
import xml.etree.ElementTree as ET
import requests

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_PORT,
                                 CONF_USERNAME, CONF_PASSWORD,
                                 CONF_BINARY_SENSORS, CONF_SENSORS,
                                 CONF_SWITCHES, CONF_MONITORED_CONDITIONS)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'android_ip_webcam'

DATA_IP_WEBCAM = 'android_ip_webcam'

DEFAULT_NAME = 'IP Webcam'

DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 10

ATTR_VID_CONNS = 'Video Connections'
ATTR_AUD_CONNS = 'Audio Connections'

STATUS_KEY_MAP = {
    'adet_limit': 'Audio Trigger Limit',
    'antibanding': 'Anti-banding',
    'audio_only': 'Audio Only',
    'coloreffect': 'Color Effect',
    'exposure': 'Exposure Level',
    'exposure_lock': 'Exposure Lock',
    'ffc': 'Front-facing Camera',
    'flashmode': 'Flash Mode',
    'focus': 'Focus',
    'focus_homing': 'Focus Homing',
    'focus_region': 'Focus Region',
    'focusmode': 'Focus Mode',
    'gps_active': 'GPS Active',
    'idle': 'Idle',
    'ip_address': 'IP Address',
    'ivideon_streaming': 'Ivideon Streaming',
    'mirror_flip': 'Mirror Flip',
    'motion_detect': 'Motion Detection',
    'motion_limit': 'Motion Limit',
    'night_vision': 'Night Vision',
    'night_vision_average': 'Night Vision Average',
    'night_vision_gain': 'Night Vision Gain',
    'orientation': 'Orientation',
    'overlay': 'Overlay',
    'photo_size': 'Photo Size',
    'quality': 'Quality',
    'scenemode': 'Scene Mode',
    'torch': 'Torch',
    'video_chunk_len': 'Video Chunk Length',
    'video_recording': 'Video Recording',
    'video_size': 'Video Size',
    'whitebalance': 'White Balance',
    'whitebalance_lock': 'White Balance Lock',
    'zoom': 'Zoom'
}

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(cv.ensure_list)
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Inclusive(CONF_USERNAME, 'authentication'): cv.string,
        vol.Inclusive(CONF_PASSWORD, 'authentication'): cv.string,
        vol.Optional(CONF_SWITCHES): SENSOR_SCHEMA,
        vol.Optional(CONF_SENSORS): SENSOR_SCHEMA,
        vol.Optional(CONF_BINARY_SENSORS): SENSOR_SCHEMA
    })
}, extra=vol.ALLOW_EXTRA)

ALLOWED_ORIENTATIONS = ['landscape', 'upsidedown', 'portrait',
                        'upsidedown_portrait']


def setup(hass, config):
    """Setup the IP Webcam component."""
    conf = config[DOMAIN]
    host = conf[CONF_HOST]
    hass.data[DATA_IP_WEBCAM][host] = {'status': {}, 'sensors': {}}

    binary_sensor_config = conf.get(CONF_BINARY_SENSORS, {})
    discovery.load_platform(hass, 'binary_sensor', DOMAIN,
                            binary_sensor_config, config)

    discovery.load_platform(hass, 'camera', DOMAIN, {}, config)

    sensor_config = conf.get(CONF_SENSORS, {})
    discovery.load_platform(hass, 'sensor', DOMAIN, sensor_config, config)

    switch_config = conf.get(CONF_SWITCHES, {})
    discovery.load_platform(hass, 'switch', DOMAIN, switch_config, config)

    return True


class IPWebcam(Entity):
    """The Android device running IP Webcam."""

    def __init__(self, name, host, username, port, password):
        """Initialize the data oject."""
        self._name = name
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._status_data = None
        self._sensor_data = None
        self._sensor_updated_at = datetime.utcnow()
        self.update()

    @property
    def _base_url(self):
        """Return the base url for endpoints."""
        return 'http://{}:{}'.format(self._host, self._port)

    def _request(self, path, resp='xml'):
        """Make the actual request and return the parsed response."""
        url = '{}{}'.format(self._base_url, path)

        auth_tuple = ()

        if self._username is not None and self._password is not None:
            auth_tuple = (self._username, self._password)

        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT,
                                    auth=auth_tuple)
            if resp == 'xml':
                root = ET.fromstring(response.text)
                print('GOT XML', root)
                return root
            elif resp == 'json':
                return response.json()
        except requests.exceptions.HTTPError:
            return {'device_state': 'error'}
        except requests.exceptions.RequestException:
            return {'device_state': 'offline'}

    def update_status(self):
        """Get updated status information from IP Webcam."""
        return self._request('/status.json?show_avail=1', resp='json')

    def update_sensors(self):
        """Get updated sensor information from IP Webcam."""
        unix_time = dt_util.as_timestamp(self._sensor_updated_at)
        url = '/sensors.json?from={}'.format(unix_time)
        response = self._request(url, resp='json')
        self._sensor_updated_at = datetime.utcnow()
        return response

    def update(self):
        """Fetch the latest data from IP Webcam."""
        self._status_data = self.update_status()
        self._sensor_data = self.update_sensors()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state_attr = {}
        state_attr[ATTR_VID_CONNS] = self._status_data.get('video_connections')
        state_attr[ATTR_AUD_CONNS] = self._status_data.get('audio_connections')
        for (key, val) in self._status_data.get('curvals'):
            if val == 'on' or val == 'off':
                val = (val == 'on')

            try:
                val = float(val)
            except ValueError:
                val = val

            state_attr[STATUS_KEY_MAP[key]] = val
        return state_attr

    def change_setting(self, key, val):
        """Change a setting."""
        if isinstance(val, bool):
            payload = 'on' if val else 'off'
        else:
            payload = val
        return self._request('/settings/{}?set={}'.format(key, payload))

    def torch(self, activate=True):
        """Enable/disable the torch."""
        path = '/enabletorch' if activate else '/disabletorch'
        return self._request(path)

    def focus(self, activate=True):
        """Enable/disable camera focus."""
        path = '/focus' if activate else '/nofocus'
        return self._request(path)

    def set_front_facing_camera(self, activate=True):
        """Enable/disable the front-facing camera."""
        return self.change_setting('ffc', activate)

    def set_night_vision(self, activate=True):
        """Enable/disable night vision."""
        return self.change_setting('night_vision', activate)

    def set_overlay(self, activate=True):
        """Enable/disable the video overlay."""
        return self.change_setting('overlay', activate)

    def set_gps_active(self, activate=True):
        """Enable/disable GPS."""
        return self.change_setting('gps_active', activate)

    def set_quality(self, quality: int=100):
        """Set the video quality."""
        return self.change_setting('quality', quality)

    def set_orientation(self, orientation: str='landscape'):
        """Set the video orientation."""
        if orientation not in ALLOWED_ORIENTATIONS:
            _LOGGER.debug('%s is not a valid orientation', orientation)
            return False
        return self.change_setting('orientation', orientation)

    def set_zoom(self, zoom: int):
        """Set the zoom level."""
        return self._request('/settings/ptz?zoom={}'.format(zoom))
