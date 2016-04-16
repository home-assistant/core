"""
Support for myStrom switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.mystrom/
"""
import logging

import requests

from homeassistant.components.switch import SwitchDevice

DEFAULT_NAME = 'myStrom Switch'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return myStrom switch."""
    host = config.get('host')

    if host is None:
        _LOGGER.error('Missing required variable: host')
        return False

    resource = 'http://{}'.format(host)

    try:
        requests.get(resource, timeout=10)
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to device %s. "
                      "Please check the IP address in the configuration file",
                      host)
        return False

    add_devices([MyStromSwitch(
        config.get('name', DEFAULT_NAME),
        resource)])


class MyStromSwitch(SwitchDevice):
    """Representation of a myStrom switch."""

    def __init__(self, name, resource):
        """Initialize the myStrom switch."""
        self._state = False
        self._name = name
        self._resource = resource
        self.consumption = 0

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def current_power_mwh(self):
        """Return the urrent power consumption in mWh."""
        return self.consumption

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        try:
            request = requests.get('{}/relay'.format(self._resource),
                                   params={'state': '1'},
                                   timeout=10)
            if request.status_code == 200:
                self._state = True
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Can't turn on %s. Is device offline?",
                          self._resource)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        try:
            request = requests.get('{}/relay'.format(self._resource),
                                   params={'state': '0'},
                                   timeout=10)
            if request.status_code == 200:
                self._state = False
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Can't turn on %s. Is device offline?",
                          self._resource)

    def update(self):
        """Get the latest data from REST API and update the state."""
        try:
            request = requests.get('{}/report'.format(self._resource),
                                   timeout=10)
            data = request.json()
            self._state = bool(data['relay'])
            self.consumption = data['power']
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to device '%s'. Is device offline?",
                          self._resource)
