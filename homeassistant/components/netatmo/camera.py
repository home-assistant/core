"""Support for the Netatmo cameras."""
import logging

import requests
import voluptuous as vol

from homeassistant.components.camera import (
    PLATFORM_SCHEMA, Camera, SUPPORT_STREAM)
from homeassistant.const import (CONF_VERIFY_SSL, STATE_ON, STATE_OFF)
from homeassistant.helpers import config_validation as cv

from .const import DATA_NETATMO_AUTH
from . import CameraData

_LOGGER = logging.getLogger(__name__)

CONF_HOME = 'home'
CONF_CAMERAS = 'cameras'
CONF_QUALITY = 'quality'

DEFAULT_QUALITY = 'high'

VALID_QUALITIES = ['high', 'medium', 'low', 'poor']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    vol.Optional(CONF_HOME): cv.string,
    vol.Optional(CONF_CAMERAS, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_QUALITY, default=DEFAULT_QUALITY):
        vol.All(cv.string, vol.In(VALID_QUALITIES)),
})

_BOOL_TO_STATE = {True: STATE_ON, False: STATE_OFF}

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up access to Netatmo cameras."""
    home = config.get(CONF_HOME)
    verify_ssl = config.get(CONF_VERIFY_SSL, True)
    quality = config.get(CONF_QUALITY, DEFAULT_QUALITY)
    import pyatmo

    auth = hass.data[DATA_NETATMO_AUTH]

    try:
        data = CameraData(hass, auth, home)
        for camera_name in data.get_camera_names():
            camera_type = data.get_camera_type(camera=camera_name, home=home)
            if CONF_CAMERAS in config:
                if config[CONF_CAMERAS] != [] and \
                   camera_name not in config[CONF_CAMERAS]:
                    continue
            add_entities([NetatmoCamera(data, camera_name, home,
                                        camera_type, verify_ssl, quality)])
        data.get_persons()
    except pyatmo.NoDevice:
        return None


class NetatmoCamera(Camera):
    """Representation of the images published from a Netatmo camera."""

    def __init__(self, data, camera_name, home, camera_type, verify_ssl,
                 quality):
        """Set up for access to the Netatmo camera images."""
        super(NetatmoCamera, self).__init__()
        self._data = data
        self._camera_name = camera_name
        self._home = home
        if home:
            self._name = home + ' / ' + camera_name
        else:
            self._name = camera_name
        self._cameratype = camera_type
        self._verify_ssl = verify_ssl
        self._quality = quality

        # URLs.
        self._vpnurl, self._localurl = self._data.camera_data.cameraUrls(
            camera=self._camera_name
        )

        # Monitoring status.
        self._status = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
            )["status"]
        if self._status == 'on':
            self._motion_detection_enabled = True
        else:
            self._motion_detection_enabled = False

        # SD Card status
        self._sd_status = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
            )["sd_status"]
        
        # Power status
        self._alim_status = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
            )["alim_status"]

        # Is local
        self._is_local = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
            )["is_local"]

        # VPN URL
        self._vpn_url = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
            )["vpn_url"]

        if self._alim_status == 'on':            
            self.is_streaming = True
        else:
            self.is_streaming = False

    # Entity method overrides
    def update(self):
        """Update entity status."""
        # Refresh camera data.
        self._data.update()

        # URLs.
        self._vpnurl, self._localurl = self._data.camera_data.cameraUrls(
            camera=self._camera_name
        )

        # Monitoring status.
        self._status = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
            )["status"]
        if self._status == 'on':
            self._motion_detection_enabled = True
        else:
            self._motion_detection_enabled = False

        # SD Card status
        self._sd_status = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
            )["sd_status"]
        
        # Power status
        self._alim_status = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
            )["alim_status"]

        # Is local
        self._is_local = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
            )["is_local"]

        # VPN URL
        self._vpn_url = self._data.camera_data.cameraByName(
            camera=self._camera_name, home=self._home
            )["vpn_url"]

        if self._alim_status == 'on':            
            self.is_streaming = True
        else:
            self.is_streaming = False


    def camera_image(self):
        """Return a still image response from the camera."""
        try:
            if self._localurl:
                response = requests.get('{0}/live/snapshot_720.jpg'.format(
                    self._localurl), timeout=10)
            elif self._vpnurl:
                response = requests.get('{0}/live/snapshot_720.jpg'.format(
                    self._vpnurl), timeout=10, verify=self._verify_ssl)
            else:
                _LOGGER.error("Welcome VPN URL is None")
                self._data.update()
                (self._vpnurl, self._localurl) = \
                    self._data.camera_data.cameraUrls(camera=self._camera_name)
                return None
        except requests.exceptions.RequestException as error:
            _LOGGER.error("Welcome URL changed: %s", error)
            self._data.update()
            (self._vpnurl, self._localurl) = \
                self._data.camera_data.cameraUrls(camera=self._camera_name)
            return None
        return response.content

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def name(self):
        """Return the name of this Netatmo camera device."""
        return self._name

    @property
    def brand(self):
        """Return the camera brand."""
        return "Netatmo"

    @property
    def model(self):
        """Return the camera model."""
        if self._cameratype == "NOC":
            return "Presence"
        if self._cameratype == "NACamera":
            return "Welcome"
        return None

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_STREAM

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return bool(self._status == 'on')

    async def stream_source(self):
        """Return the stream source."""
        url = '{0}/live/files/{1}/index.m3u8'
        if self._localurl:
            return url.format(self._localurl, self._quality)
        return url.format(self._vpnurl, self._quality)

    @property
    def device_state_attributes(self):
        """Return the Netatmo-specific camera state attributes."""

        attr = {}
        attr['status'] = self._status
        attr['sd_status'] = self._sd_status
        attr['alim_status'] = self._alim_status
        attr['is_local'] = self._is_local
        attr['vpn_url'] = self._vpn_url

        return attr

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._motion_detection_enabled

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        self._enable_motion_detection(True)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self._enable_motion_detection(False)

    def _enable_motion_detection(self, enable):
        """Enable or disable motion detection."""
        try:
            if self._localurl:
                response = requests.get('{0}/command/changestatus?status={1}'.format(
                    self._localurl, _BOOL_TO_STATE.get(enable)), timeout=10)
                self._motion_detection_enabled = enable
            elif self._vpnurl:
                response = requests.get('{0}/command/changestatus?status={1}'.format(
                    self._vpnurl, _BOOL_TO_STATE.get(enable)), timeout=10, verify=self._verify_ssl)
                self._motion_detection_enabled = enable
            else:
                _LOGGER.error("Welcome VPN URL is None")
                self._data.update()
                (self._vpnurl, self._localurl) = \
                    self._data.camera_data.cameraUrls(camera=self._camera_name)
                return None
        except requests.exceptions.RequestException as error:
            _LOGGER.error("Welcome URL changed: %s", error)
            self._data.update()
            (self._vpnurl, self._localurl) = \
                self._data.camera_data.cameraUrls(camera=self._camera_name)
            return None

        self.schedule_update_ha_state(True)
        return response.content
