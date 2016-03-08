"""
Support for device running with the aREST RESTful framework.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.arest/
"""
import logging

import requests

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import DEVICE_DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the aREST switches."""
    resource = config.get('resource', None)

    try:
        response = requests.get(resource, timeout=10)
    except requests.exceptions.MissingSchema:
        _LOGGER.error("Missing resource or schema in configuration. "
                      "Add http:// to your URL.")
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to device at %s. "
                      "Please check the IP address in the configuration file.",
                      resource)
        return False

    dev = []
    pins = config.get('pins', {})
    for pinnum, pin in pins.items():
        dev.append(ArestSwitchPin(resource,
                                  config.get('name', response.json()['name']),
                                  pin.get('name'),
                                  pinnum))

    functions = config.get('functions', {})
    for funcname, func in functions.items():
        dev.append(ArestSwitchFunction(resource,
                                       config.get('name',
                                                  response.json()['name']),
                                       func.get('name'),
                                       funcname))

    add_devices(dev)


class ArestSwitchBase(SwitchDevice):
    """representation of an aREST switch."""

    def __init__(self, resource, location, name):
        """Initialize the switch."""
        self._resource = resource
        self._name = '{} {}'.format(location.title(), name.title()) \
                     or DEVICE_DEFAULT_NAME
        self._state = None

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state


class ArestSwitchFunction(ArestSwitchBase):
    """Representation of an aREST switch."""

    def __init__(self, resource, location, name, func):
        """Initialize the switch."""
        super().__init__(resource, location, name)
        self._func = func

        request = requests.get('{}/{}'.format(self._resource, self._func),
                               timeout=10)

        if request.status_code is not 200:
            _LOGGER.error("Can't find function. Is device offline?")
            return

        try:
            request.json()['return_value']
        except KeyError:
            _LOGGER.error("No return_value received. "
                          "Is the function name correct.")
        except ValueError:
            _LOGGER.error("Response invalid. Is the function name correct.")

    def turn_on(self, **kwargs):
        """Turn the device on."""
        request = requests.get('{}/{}'.format(self._resource, self._func),
                               timeout=10, params={"params": "1"})

        if request.status_code == 200:
            self._state = True
        else:
            _LOGGER.error("Can't turn on function %s at %s. "
                          "Is device offline?",
                          self._func, self._resource)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        request = requests.get('{}/{}'.format(self._resource, self._func),
                               timeout=10, params={"params": "0"})

        if request.status_code == 200:
            self._state = False
        else:
            _LOGGER.error("Can't turn off function %s at %s. "
                          "Is device offline?",
                          self._func, self._resource)

    def update(self):
        """Get the latest data from aREST API and update the state."""
        request = requests.get('{}/{}'.format(self._resource,
                                              self._func), timeout=10)
        self._state = request.json()['return_value'] != 0


class ArestSwitchPin(ArestSwitchBase):
    """Representation of an aREST switch. Based on digital I/O."""

    def __init__(self, resource, location, name, pin):
        """Initialize the switch."""
        super().__init__(resource, location, name)
        self._pin = pin

        request = requests.get('{}/mode/{}/o'.format(self._resource,
                                                     self._pin), timeout=10)
        if request.status_code is not 200:
            _LOGGER.error("Can't set mode. Is device offline?")

    def turn_on(self, **kwargs):
        """Turn the device on."""
        request = requests.get('{}/digital/{}/1'.format(self._resource,
                                                        self._pin), timeout=10)
        if request.status_code == 200:
            self._state = True
        else:
            _LOGGER.error("Can't turn on pin %s at %s. Is device offline?",
                          self._pin, self._resource)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        request = requests.get('{}/digital/{}/0'.format(self._resource,
                                                        self._pin), timeout=10)
        if request.status_code == 200:
            self._state = False
        else:
            _LOGGER.error("Can't turn off pin %s at %s. Is device offline?",
                          self._pin, self._resource)

    def update(self):
        """Get the latest data from aREST API and update the state."""
        request = requests.get('{}/digital/{}'.format(self._resource,
                                                      self._pin), timeout=10)
        self._state = request.json()['return_value'] != 0
