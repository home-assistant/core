"""
Support turning on/off motion detection on Amcrest IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.amcrest/
"""

import logging
import voluptuous as vol
from requests.exceptions import HTTPError, ConnectTimeout

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_HOST, CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_PORT, STATE_UNKNOWN, STATE_OFF, STATE_ON)
from homeassistant.helpers.entity import ToggleEntity

REQUIREMENTS = ['amcrest==1.2.0']
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Amcrest'
DEFAULT_PORT = 80

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for an Amcrest IP Camera."""
    from amcrest import AmcrestCamera

    camera = AmcrestCamera(
        config.get(CONF_HOST), config.get(CONF_PORT),
        config.get(CONF_USERNAME), config.get(CONF_PASSWORD)).camera

    try:
        camera.current_time
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Amcrest camera: %s", str(ex))
        return False

    add_devices([AmcrestMotionSwitch(config, camera)])
    return True


class AmcrestMotionSwitch(ToggleEntity):
    """Representation of a switch to toggle on/off motion detection."""


    def __init__(self, device_info, camera):
        """Initialize the switch."""
        # XXX DAP wtf is this: super(AmcrestSensor, self).__init__()
        #self._attrs = {}
        self._camera = camera
        self._name = device_info.get(CONF_NAME)
        #self._icon = 'mdi:{}'.format(SENSOR_TYPES.get(self._sensor_type)[2])
        self._state = STATE_UNKNOWN


    @property
    def should_poll(self):
        """Poll for status regularly."""
        return True


    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name


    @property
    def state(self):
        """Return the state of the motion detection."""
        return self._state


    @property
    def is_on(self):
        """Return true if motion detection is on."""
        return self._state == STATE_ON


    #@property
    #def device_state_attributes(self):
    #    """Return the state attributes."""
    #    return self._attrs
    #
    #
    #@property
    #def icon(self):
    #    """Icon to use in the frontend, if any."""
    #    return self._icon


    def turn_on(self, **kwargs):
        """Turn the device on."""
        _LOGGER.info("Turning on Motion Detection")
        self._camera.motion_detection = 'true'


    def turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGER.info("Turning off Motion Detection")
        self._camera.motion_detection = 'false'


    def update(self):
        """Update Motion Detection state."""
        _LOGGER.debug("Pulling Motion Detection data from %s sensor.", self._name)
        detection = self._camera.is_motion_detector_on()
        self._state = STATE_ON if detection else STATE_OFF
        #self._attrs['Motion Detection Config'] = self._camera.motion_detection
