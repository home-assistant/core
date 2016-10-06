"""
Support for Harmony remote control devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/harmony/

Example configuration.yaml
harmony:
- name: Bedroom
  username: EMAIL
  password: PASSWORD
  host: 10.168.1.13
  port: 5222
- name: Family Room
  username: EMAIL
  password: PASSWORD
  host: 10.168.1.16
  port: 5222
"""

from homeassistant.components.discovery import load_platform
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_PORT, ATTR_ENTITY_ID
import logging
import pyharmony
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyharmony>=1.0.5']
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = 30
GROUP_NAME_ALL_HARMONY = 'all harmony devices'

HARMONY_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})



DOMAIN = 'harmony'
HARMONY = {}

def setup(hass, config):
    """Track states and offer events for Harmony devices."""

    global HARMONY

    for hub in config[DOMAIN]:
        #populate global variable
        HARMONY[hub[CONF_NAME]] = {}
        HARMONY[hub[CONF_NAME]]['device'] = \
            HarmonyDevice(hub[CONF_NAME],
                          hub[CONF_USERNAME],
                          hub[CONF_PASSWORD],
                          hub[CONF_HOST],
                          hub[CONF_PORT])
        HARMONY[hub[CONF_NAME]]['activities'] = \
            pyharmony.ha_get_activities(hub[CONF_USERNAME],
                                        hub[CONF_PASSWORD],
                                        hub[CONF_HOST],
                                        hub[CONF_PORT])

        #create configuration file containing activites, devices, and commands
        HARMONY_CONF_FILE = hass.config.path('harmonyConf-' + hub[CONF_NAME] + '.txt')
        pyharmony.ha_get_config_file(hub[CONF_USERNAME],
                                     hub[CONF_PASSWORD],
                                     hub[CONF_HOST],
                                     hub[CONF_PORT],
                                     HARMONY_CONF_FILE)

    # create sensor for each Harmony device to display current activity
    load_platform(hass, 'sensor', DOMAIN )

    # create switch for each activity from each Harmony device
    load_platform(hass, 'switch', DOMAIN)

    #create remote object and start services
    load_platform(hass, 'remote', DOMAIN, {})

    return True

class HarmonyDevice(Entity):
    """Representation of a base Harmony device"""
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
    def state(self):
        """Return the state of the Harmony device."""
        return self.get_status()


    @property
    def config(self):
        '''Return the device's configuration information'''
        return {'email':self._email,
                'password':self._password,
                'ip':self._ip,
                'port':self._port}

    def get_status(self):
        return pyharmony.ha_get_current_activity(self._email, self._password, self._ip, self._port)

    def turn_on(self, activity_id):
        """Turn the switch on."""
        pyharmony.ha_start_activity(self._email, self._password, self._ip, self._port, activity_id)
