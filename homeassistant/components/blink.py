"""
Support for Blink Home Camera System.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/blink/
"""
import logging
from datetime import timedelta
import requests
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_USERNAME,
                                 CONF_PASSWORD,
                                 ATTR_FRIENDLY_NAME,
                                 ATTR_ARMED)
from homeassistant.helpers import discovery
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'blink'
REQUIREMENTS = ['blinkpy==0.5.2']

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=180)
MIN_TIME_BETWEEN_FORCED_UPDATES = timedelta(seconds=5)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

ARM_SYSTEM_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ARMED): cv.boolean
})

ARM_CAMERA_SCHEMA = vol.Schema({
    vol.Required(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_ARMED): cv.boolean
})

SNAP_PICTURE_SCHEMA = vol.Schema({
    vol.Required(ATTR_FRIENDLY_NAME): cv.string
})


class BlinkSystem(object):
    """Blink System class."""

    def __init__(self, config_info):
        """Initialize the system."""
        import blinkpy
        self.blink = blinkpy.Blink(username=config_info[DOMAIN][CONF_USERNAME],
                                   password=config_info[DOMAIN][CONF_PASSWORD])
        self.blink.setup_system()
        self._header = {}
        self.ignore_throttle = False

    @Throttle(MIN_TIME_BETWEEN_UPDATES, MIN_TIME_BETWEEN_FORCED_UPDATES)
    def image_request(self, image_url, **kwargs):
        """Request an image from Blink servers."""
        _LOGGER.info("Requesting image from Blink servers.")
        response = requests.get(image_url, headers=self._header, stream=True)
        if self.ignore_throttle:
            self.ignore_throttle = False
        return response

    @Throttle(MIN_TIME_BETWEEN_UPDATES, MIN_TIME_BETWEEN_FORCED_UPDATES)
    def update(self, **kwargs):
        """Check auth token and update system."""
        # Grab random camera header, doesn't matter which one
        if not self._header:
            camera_name = list(self.blink.cameras.keys())[0]
            self._header = self.blink.cameras[camera_name].header
            _LOGGER.info("Retrieving header from %s.", camera_name)

        resp = requests.get(self.blink.urls.networks_url,
                            headers=self._header)
        if resp.status_code is not 200:
            # Can't get device data, need to get new auth token
            _LOGGER.info("Received status code %d, getting new token.",
                         resp.status_code)
            self.blink.get_auth_token()
            self.blink.set_links()
            self._header = {}

        self.blink.refresh()

    def force_update(self):
        """Force a system update."""
        self.ignore_throttle = True
        self.update(no_throttle=True)


def setup(hass, config):
    """Setup Blink System."""
    hass.data[DOMAIN] = BlinkSystem(config)
    discovery.load_platform(hass, 'camera', DOMAIN, {}, config)
    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, {}, config)

    def snap_picture(call):
        """Take a picture."""
        cameras = hass.data[DOMAIN].blink.cameras
        name = call.data.get(ATTR_FRIENDLY_NAME, '')
        if name in cameras:
            cameras[name].snap_picture()

    def arm_camera(call):
        """Arm a camera."""
        cameras = hass.data[DOMAIN].blink.cameras
        name = call.data.get(ATTR_FRIENDLY_NAME, '')
        value = call.data.get(ATTR_ARMED, True)
        if name in cameras:
            cameras[name].set_motion_detect(value)

    def arm_system(call):
        """Arm the system."""
        value = call.data.get(ATTR_ARMED, True)
        hass.data[DOMAIN].blink.arm = value
        hass.data[DOMAIN].update()

    def force_update(call):
        """Force an update."""
        hass.data[DOMAIN].force_update()

    hass.services.register(DOMAIN, 'snap_picture', snap_picture,
                           schema=SNAP_PICTURE_SCHEMA)
    hass.services.register(DOMAIN, 'arm_camera', arm_camera,
                           schema=ARM_CAMERA_SCHEMA)
    hass.services.register(DOMAIN, 'arm_system', arm_system,
                           schema=ARM_SYSTEM_SCHEMA)
    hass.services.register(DOMAIN, 'force_update', force_update)

    return True
