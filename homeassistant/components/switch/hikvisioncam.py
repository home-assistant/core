"""
Support turning on/off motion detection on Hikvision cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.hikvision/
"""
import logging

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, STATE_OFF, STATE_ON)
from homeassistant.helpers.entity import ToggleEntity

_LOGGING = logging.getLogger(__name__)
REQUIREMENTS = ['hikvision==0.4']
# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup Hikvision camera."""
    import hikvision.api
    from hikvision.error import HikvisionError, MissingParamError

    host = config.get(CONF_HOST, None)
    port = config.get('port', "80")
    name = config.get('name', "Hikvision Camera Motion Detection")
    username = config.get(CONF_USERNAME, "admin")
    password = config.get(CONF_PASSWORD, "12345")

    try:
        hikvision_cam = hikvision.api.CreateDevice(
            host, port=port, username=username,
            password=password, is_https=False)
    except MissingParamError as param_err:
        _LOGGING.error("Missing required param: %s", param_err)
        return False
    except HikvisionError as conn_err:
        _LOGGING.error("Unable to connect: %s", conn_err)
        return False

    add_devices_callback([
        HikvisionMotionSwitch(name, hikvision_cam)
    ])


class HikvisionMotionSwitch(ToggleEntity):
    """Representation of a switch to toggle on/off motion detection."""

    def __init__(self, name, hikvision_cam):
        """Initialize the switch."""
        self._name = name
        self._hikvision_cam = hikvision_cam
        self._state = STATE_OFF

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
        """Return the state of the device if any."""
        return self._state

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """Turn the device on."""
        _LOGGING.info("Turning on Motion Detection ")
        self._hikvision_cam.enable_motion_detection()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGING.info("Turning off Motion Detection ")
        self._hikvision_cam.disable_motion_detection()

    def update(self):
        """Update Motion Detection state."""
        enabled = self._hikvision_cam.is_motion_detection_enabled()
        _LOGGING.info('enabled: %s', enabled)

        self._state = STATE_ON if enabled else STATE_OFF
