"""
homeassistant.components.switch.edimax
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Edimax switches.

Configuration:

To use the Edimax switch you will need to add something like the following to
your config/configuration.yaml.

switch:
    platform: edimax
    host: 192.168.1.32
    username: YOUR_USERNAME
    password: YOUR_PASSWORD
    name: Edimax Smart Plug

Variables:

host
*Required
This is the IP address of your Edimax switch. Example: 192.168.1.32

username
*Required
Your username to access your Edimax switch.

password
*Required
Your password.

name
*Optional
The name to use when displaying this switch instance.
"""
import logging

from homeassistant.helpers import validate_config
from homeassistant.components.switch import SwitchDevice, DOMAIN
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD,\
    CONF_NAME

# constants
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = '1234'
DEVICE_DEFAULT_NAME = 'Edimax Smart Plug'
REQUIREMENTS = ['https://github.com/rkabadi/pyedimax/archive/' +
                '365301ce3ff26129a7910c501ead09ea625f3700.zip']

# setup logger
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Edimax Smart Plugs. """
    try:
        # pylint: disable=no-name-in-module, import-error
        from pyedimax.smartplug import SmartPlug
    except ImportError:
        _LOGGER.error('Failed to import pyedimax')
        return False

    # pylint: disable=global-statement
    # check for required values in configuration file
    if not validate_config({DOMAIN: config},
                           {DOMAIN: [CONF_HOST]},
                           _LOGGER):
        return False

    host = config.get(CONF_HOST)
    auth = (config.get(CONF_USERNAME, DEFAULT_USERNAME),
            config.get(CONF_PASSWORD, DEFAULT_PASSWORD))
    name = config.get(CONF_NAME, DEVICE_DEFAULT_NAME)

    add_devices_callback([SmartPlugSwitch(SmartPlug(host, auth), name)])


class SmartPlugSwitch(SwitchDevice):
    """ Represents an Edimax Smart Plug switch. """
    def __init__(self, smartplug, name):
        self.smartplug = smartplug
        self._name = name

    @property
    def name(self):
        """ Returns the name of the Smart Plug, if any. """
        return self._name

    @property
    def current_power_mwh(self):
        """ Current power usage in mwh. """
        try:
            return float(self.smartplug.now_power) / 1000000.0
        except ValueError:
            return None

    @property
    def today_power_mw(self):
        """ Today total power usage in mw. """
        try:
            return float(self.smartplug.now_energy_day) / 1000.0
        except ValueError:
            return None

    @property
    def is_on(self):
        """ True if switch is on. """
        return self.smartplug.state == 'ON'

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.smartplug.state = 'ON'

    def turn_off(self):
        """ Turns the switch off. """
        self.smartplug.state = 'OFF'
