"""
homeassistant.components.switch.hikvision
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support turning on/off motion detection on Hikvision cameras.

Note: Currently works using default https port only.

CGI API Guide: http://bit.ly/1RuyUuF

Configuration:

To use the Hikvision motion detection switch you will need to add something
like the following to your config/configuration.yaml

switch:
    platform: hikvisioncam
    name: Hikvision Cam 1 Motion Detection
    host: 192.168.1.32
    username: YOUR_USERNAME
    password: YOUR_PASSWORD

Variables:

host
*Required
This is the IP address of your Hikvision camera. Example: 192.168.1.32

username
*Required
Your Hikvision camera username.

password
*Required
Your Hikvision camera username.

name
*Optional
The name to use when displaying this switch instance.
"""
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
import logging

try:
    import hikvision.api
    from hikvision.error import HikvisionError, MissingParamError
except ImportError:
    hikvision.api = None

_LOGGING = logging.getLogger(__name__)
REQUIREMENTS = ['hikvision==0.4']
# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Setup Hikvision Camera config. """

    host = config.get(CONF_HOST, None)
    port = config.get('port', "80")
    name = config.get('name', "Hikvision Camera Motion Detection")
    username = config.get(CONF_USERNAME, "admin")
    password = config.get(CONF_PASSWORD, "12345")

    if hikvision.api is None:
        _LOGGING.error((
            "Failed to import hikvision. Did you maybe not install the "
            "'hikvision' dependency?"))

        return False

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

    """ Provides a switch to toggle on/off motion detection. """

    def __init__(self, name, hikvision_cam):
        self._name = name
        self._hikvision_cam = hikvision_cam
        self._state = STATE_OFF

    @property
    def should_poll(self):
        """ Poll for status regularly. """
        return True

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device if any. """
        return self._state

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """ Turn the device on. """

        _LOGGING.info("Turning on Motion Detection ")
        self._hikvision_cam.enable_motion_detection()

    def turn_off(self, **kwargs):
        """ Turn the device off. """

        _LOGGING.info("Turning off Motion Detection ")
        self._hikvision_cam.disable_motion_detection()

    def update(self):
        """ Update Motion Detection state """
        enabled = self._hikvision_cam.is_motion_detection_enabled()
        _LOGGING.info('enabled: %s', enabled)

        self._state = STATE_ON if enabled else STATE_OFF
