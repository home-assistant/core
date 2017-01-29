"""
Support for IP Webcam, an Android app that acts as a full-featured webcam.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/android_ip_webcam/
"""
import logging
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import requests
from urllib.parse import quote

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
import homeassistant.util.dt as dt_util
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_PORT,
                                 CONF_USERNAME, CONF_PASSWORD, CONF_SENSORS,
                                 CONF_SWITCHES)
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'android_ip_webcam'

DATA_IP_WEBCAM = 'android_ip_webcam'

DEFAULT_NAME = 'IP Webcam'

DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 10

ATTR_VID_CONNS = 'Video Connections'
ATTR_AUD_CONNS = 'Audio Connections'

KEY_MAP = {
    'audio_connections': 'Audio Connections',
    'adet_limit': 'Audio Trigger Limit',
    'antibanding': 'Anti-banding',
    'audio_only': 'Audio Only',
    'battery_level': 'Battery Level',
    'battery_temp': 'Battery Temperature',
    'battery_voltage': 'Battery Voltage',
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
    'ip_address': 'IPv4 Address',
    'ipv6_address': 'IPv6 Address',
    'ivideon_streaming': 'Ivideon Streaming',
    'light': 'Light Level',
    'mirror_flip': 'Mirror Flip',
    'motion': 'Motion',
    'motion_active': 'Motion Active',
    'motion_detect': 'Motion Detection',
    'motion_event': 'Motion Event',
    'motion_limit': 'Motion Limit',
    'night_vision': 'Night Vision',
    'night_vision_average': 'Night Vision Average',
    'night_vision_gain': 'Night Vision Gain',
    'orientation': 'Orientation',
    'overlay': 'Overlay',
    'photo_size': 'Photo Size',
    'pressure': 'Pressure',
    'proximity': 'Proximity',
    'quality': 'Quality',
    'scenemode': 'Scene Mode',
    'sound': 'Sound',
    'sound_event': 'Sound Event',
    'sound_timeout': 'Sound Timeout',
    'torch': 'Torch',
    'video_connections': 'Video Connections',
    'video_chunk_len': 'Video Chunk Length',
    'video_recording': 'Video Recording',
    'video_size': 'Video Size',
    'whitebalance': 'White Balance',
    'whitebalance_lock': 'White Balance Lock',
    'zoom': 'Zoom'
}

ICON_MAP = {
    'audio_connections': 'mdi:speaker',
    'battery_level': 'mdi:battery',
    'battery_temp': 'mdi:thermometer',
    'battery_voltage': 'mdi:battery-charging-100',
    'exposure_lock': 'mdi:camera',
    'ffc': 'mdi:camera-front-variant',
    'focus': 'mdi:image-filter-center-focus',
    'gps_active': 'mdi:crosshairs-gps',
    'light': 'mdi:flashlight',
    'motion': 'mdi:run',
    'night_vision': 'mdi:weather-night',
    'overlay': 'mdi:monitor',
    'pressure': 'mdi:gauge',
    'proximity': 'mdi:map-marker-radius',
    'quality': 'mdi:quality-high',
    'sound': 'mdi:speaker',
    'sound_event': 'mdi:speaker',
    'sound_timeout': 'mdi:speaker',
    'torch': 'mdi:white-balance-sunny',
    'video_chunk_len': 'mdi:video',
    'video_connections': 'mdi:eye',
    'video_recording': 'mdi:record-rec',
    'whitebalance_lock': 'mdi:white-balance-auto'
}

SWITCHES = ['exposure_lock', 'ffc', 'focus', 'gps_active', 'night_vision',
            'overlay', 'torch', 'whitebalance_lock', 'video_recording']

SENSORS = ['audio_connections', 'battery_level', 'battery_temp',
           'battery_voltage', 'light', 'motion', 'pressure', 'proximity',
           'sound', 'video_connections']

CONF_MOTION_BINARY_SENSOR = 'motion_binary_sensor'

DEFAULT_MOTION_BINARY_SENSOR = True

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Inclusive(CONF_USERNAME, 'authentication'): cv.string,
        vol.Inclusive(CONF_PASSWORD, 'authentication'): cv.string,
        vol.Optional(CONF_SWITCHES,
                     default=SWITCHES): vol.All(cv.ensure_list,
                                                [vol.In(SWITCHES)]),
        vol.Optional(CONF_SENSORS,
                     default=SENSORS): vol.All(cv.ensure_list,
                                               [vol.In(SENSORS)]),
        vol.Optional(CONF_MOTION_BINARY_SENSOR,
                     default=DEFAULT_MOTION_BINARY_SENSOR): bool
    })
}, extra=vol.ALLOW_EXTRA)

ALLOWED_ORIENTATIONS = ['landscape', 'upsidedown', 'portrait',
                        'upsidedown_portrait']

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3)


def setup(hass, config):
    """Setup the IP Webcam component."""
    conf = config[DOMAIN]
    host = conf[CONF_HOST]
    ip_webcam = hass.data.get(DATA_IP_WEBCAM)
    if ip_webcam is None:
        hass.data[DATA_IP_WEBCAM] = {}
    hass.data[DATA_IP_WEBCAM][host] = IPWebcam(conf)

    if conf.get(CONF_MOTION_BINARY_SENSOR, False) is True:
        discovery.load_platform(hass, 'binary_sensor', DOMAIN, {}, config)

    discovery.load_platform(hass, 'camera', DOMAIN, {}, config)

    sensor_config = conf.get(CONF_SENSORS, [])
    discovery.load_platform(hass, 'sensor', DOMAIN, sensor_config, config)

    switch_config = conf.get(CONF_SWITCHES, [])
    discovery.load_platform(hass, 'switch', DOMAIN, switch_config, config)

    return True


class IPWebcam(object):
    """The Android device running IP Webcam."""

    def __init__(self, config):
        """Initialize the data oject."""
        self._config = config
        self._name = self._config.get(CONF_NAME)
        self.host = self._config.get(CONF_HOST)
        self.port = self._config.get(CONF_PORT)
        self.username = self._config.get(CONF_USERNAME)
        self.password = self._config.get(CONF_PASSWORD)
        self.status_data = None
        self.sensor_data = None
        self._sensor_updated_at = (datetime.now() - timedelta(seconds=5))
        self.update()

    @property
    def base_url(self):
        """Return the base url for endpoints."""
        return 'http://{}:{}'.format(self.host, self.port)

    def _request(self, path):
        """Make the actual request and return the parsed response."""
        url = '{}{}'.format(self.base_url, path)

        auth_tuple = ()

        if self.username is not None and self.password is not None:
            auth_tuple = (self.username, self.password)

        resp = 'json' if '.json' in path else 'xml'

        if '/startvideo' in path or '/stopvideo' in path:
            resp = 'json'

        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT,
                                    auth=auth_tuple)
            if resp == 'xml':
                return ET.fromstring(response.text)
            elif resp == 'json':
                return response.json()
        except requests.exceptions.HTTPError:
            return {'device_state': 'error'}
        except requests.exceptions.RequestException:
            return {'device_state': 'offline'}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch the latest data from IP Webcam."""
        self.status_data = self._request('/status.json')

        utime = int(dt_util.as_timestamp(self._sensor_updated_at) * 1000)
        self.sensor_data = self._request('/sensors.json?from={}'.format(utime))
        self._sensor_updated_at = datetime.now()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state_attr = {}
        state_attr[ATTR_VID_CONNS] = self.status_data.get('video_connections')
        state_attr[ATTR_AUD_CONNS] = self.status_data.get('audio_connections')
        for (key, val) in self.status_data.get('curvals').items():
            try:
                val = float(val)
            except ValueError:
                val = val

            if val == 'on' or val == 'off':
                val = (val == 'on')

            state_attr[KEY_MAP.get(key, key)] = val
        return state_attr

    @property
    def enabled_sensors(self):
        """Return the enabled sensors."""
        return list(self.sensor_data.keys())

    @property
    def current_settings(self):
        """Return a dictionary of the current settings."""
        settings = {}
        for (key, val) in self.status_data.get('curvals').items():
            try:
                val = float(val)
            except ValueError:
                val = val

            if val == 'on' or val == 'off':
                val = (val == 'on')

            settings[key] = val
        return settings

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

    def record(self, record=True, tag=None):
        """Enable/disable recording."""
        path = '/startvideo?force=1' if record else '/stopvideo?force=1'
        if record and tag is not None:
            path = '/startvideo?force=1&tag={}'.format(quote(tag))
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
