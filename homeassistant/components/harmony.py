"""
Support for Harmony remote control devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/harmony/

Example configuration.yaml
harmony:
- name: Bedroom
  username: EMAIL
  password: PASSWORD
  ip: 10.168.1.13
  port: 5222
- name: Family Room
  username: EMAIL
  password: PASSWORD
  ip: 10.168.1.16
  port: 5222
"""
from homeassistant.components.discovery import load_platform
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_PORT
from homeassistant.const import (
    STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE,
    ATTR_ENTITY_ID)
from homeassistant.components import group
import logging
import pyharmony
import voluptuous as vol
import os
from homeassistant.config import load_yaml_config_file
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyharmony>=0.2.0']
_LOGGER = logging.getLogger(__name__)
CONF_IP = 'ip'
#SCAN_INTERVAL = 30
#GROUP_NAME_ALL_HARMONY = 'all remote devices'
#ENTITY_ID_ALL_SWITCHES = group.ENTITY_ID_FORMAT.format('all_harmony')

#ENTITY_ID_FORMAT = DOMAIN + '.{}'

HARMONY_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

ATTR_VALUE1 = 'device'
ATTR_VALUE2 = 'command'
ATTR_DEFAULT = ''
DOMAIN = 'harmony'
HUB_CONF_GLOBAL = {}

def setup(hass, config):
    """Track states and offer events for switches."""

    global HUB_CONF_GLOBAL
    HUB_CONF_GLOBAL = config[DOMAIN]

    # create sensor for each Harmony device to display current activity
    load_platform(hass, 'sensor', DOMAIN )
    # create switch for each activity from each Harmony device
    load_platform(hass, 'switch', DOMAIN, {})

    return True

class HarmonyDevice(Entity):
    """Representation of a base Harmony device"""
    def __init__(self, name, username, password, ip, port):
        self._name = name
        self._email = username
        self._password = password
        self._ip = ip
        self._port = port
        self._devices = ''


    @property
    def name(self):
        """Return the name of the Harmony device"""
        return self._name


    @property
    def state(self):
        """Return the state of the Harmony device."""
        return self.get_status()


    def get_status(self):
        return pyharmony.ha_get_current_activity(self._email, self._password, self._ip, self._port)


    def send_command(self, device_id, new_command):
        pyharmony.ha_send_command(self._email, self._password, self._ip, self._port, device_id, new_command)


    def is_on(hass, entity_id=None):
        """Return if the switch is on based on the statemachine."""
        entity_id = entity_id or ENTITY_ID_ALL_SWITCHES
        if hass.states.is_state(entity_id, 'PowerOff'):
            return False
        else:
            return True