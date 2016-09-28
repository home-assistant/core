####HUB###
from homeassistant.components.discovery import load_platform
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_PORT
import logging
import pyharmony


DOMAIN = 'harmony'
REQUIREMENTS = ['pyharmony>=0.2.0']
_LOGGER = logging.getLogger(__name__)
CONF_IP = 'ip'

HUB_CONF_GLOBAL = {}

def setup(hass, config):
    global HUB_CONF_GLOBAL
    HUB_CONF_GLOBAL = config[DOMAIN]
        # write file containing activities and commands
        #HARMONY_CONF_FILE = hass.config.path('harmonyConf-' + hub[CONF_NAME] + '.txt')
    # create current activity sensor for each Harmony device
    load_platform(hass, 'sensor', DOMAIN, {})
    # create switch for each activity
    load_platform(hass, 'switch', DOMAIN, {})
    return True

class HarmonyDevice(Entity):
    """Representation of a base Harmony Device"""
    def __init__(self, name, username, password, ip, port):
        self._name = name
        self._email = username
        self._password = password
        self._ip = ip
        self._port = port

    @property
    def name(self):
        """Return the name of the Harmony device"""
        return self._name


    @property
    def state_attributes(self):
        """Return the ip address of the hub."""
        return {'ip_address':self._ip}


    def send_command(self, device_id, new_command):
        pyharmony.ha_send_command(self._email, self._password, self._ip, self._port, device_id, new_command)

