"""
homeassistant.components.switch.enigma
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enable or disable standby mode on Enigma2 receivers.

You should have a recent version of OpenWebIf installed.

There is no support for username/password authentication
at this time.

Configuration:

To use the switch you will need to add something like the
following to your config/configuration.yaml

switch:
    platform: enigma
    name: Vu Duo2
    host: 192.168.1.26
    port: 80

Variables:

host
*Required
This is the IP address of your Enigma2 box. Example: 192.168.1.32

port
*Optional
The port your Enigma2 box uses, defaults to 80. Example: 8080

name
*Optional
The name to use when displaying this Enigma2 switch instance.

"""
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import STATE_ON, STATE_OFF, CONF_HOST
import logging
try:
    import openwebif.api
    from openwebif.error import OpenWebIfError, MissingParamError
except ImportError:
    openwebif.api = None

_LOGGING = logging.getLogger(__name__)

# pylint: disable=unused-argument


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return enigma2 boxes. """

    if openwebif.api is None:
        _LOGGING.error((
            "Failed to import openwebif. Did you maybe not install the "
            "'openwebif.py' dependency?"))

        return False

    host = config.get(CONF_HOST, None)
    port = config.get('port', "80")
    name = config.get('name', "Enigma2 Active")

    try:
        e2_box = openwebif.api.CreateDevice(host, port=port)
    except MissingParamError as param_err:
        _LOGGING.error("Missing required param: %s", param_err)
        return False
    except OpenWebIfError as conn_err:
        _LOGGING.error("Unable to connect: %s", conn_err)
        return False

    add_devices_callback([
        EnigmaSwitch(name, e2_box)
    ])


class EnigmaSwitch(ToggleEntity):

    """ Provides a switch to toggle standby on an Enigma2 box. """

    def __init__(self, name, e2_box):
        self._name = name
        self._e2_box = e2_box
        self._state = STATE_OFF
        self.update()

    @property
    def should_poll(self):
        """ Need to refresh ourselves. """
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

        _LOGGING.info("Turning on Enigma ")
        self.toggle_standby()

    def turn_off(self, **kwargs):
        """ Turn the device off. """

        _LOGGING.info("Turning off Enigma ")
        self.toggle_standby()

    def toggle_standby(self):
        """
        # See http://bit.ly/1Qf9Wgv
        """
        self._e2_box.toggle_standby()

    def update(self):
        """ Update state of the sensor. """
        _LOGGING.info("updating status enigma")

        in_standby = self._e2_box.is_box_in_standby()
        _LOGGING.info('inStandby: %s', in_standby)

        if in_standby:
            self._state = STATE_OFF
        else:
            self._state = STATE_ON
