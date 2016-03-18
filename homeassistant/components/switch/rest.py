"""
Support for RESTful switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rest/
"""
import logging

import requests

from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "REST Switch"
DEFAULT_BODY_ON = "ON"
DEFAULT_BODY_OFF = "OFF"


# pylint: disable=unused-argument,
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the REST switch."""
    resource = config.get('resource')

    if resource is None:
        _LOGGER.error("Missing required variable: resource")
        return False

    try:
        requests.get(resource, timeout=10)
    except requests.exceptions.MissingSchema:
        _LOGGER.error("Missing resource or schema in configuration. "
                      "Add http:// or https:// to your URL")
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to resource/endpoint: %s", resource)
        return False

    add_devices_callback([RestSwitch(
        hass,
        config.get('name', DEFAULT_NAME),
        config.get('resource'),
        config.get('body_on', DEFAULT_BODY_ON),
        config.get('body_off', DEFAULT_BODY_OFF))])


# pylint: disable=too-many-arguments
class RestSwitch(SwitchDevice):
    """Representation of a switch that can be toggled using REST."""

    def __init__(self, hass, name, resource, body_on, body_off):
        """Initialize the REST switch."""
        self._state = None
        self._hass = hass
        self._name = name
        self._resource = resource
        self._body_on = body_on
        self._body_off = body_off

    @property
    def name(self):
        """The name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        request = requests.post(self._resource,
                                data=self._body_on,
                                timeout=10)
        if request.status_code == 200:
            self._state = True
        else:
            _LOGGER.error("Can't turn on %s. Is resource/endpoint offline?",
                          self._resource)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        request = requests.post(self._resource,
                                data=self._body_off,
                                timeout=10)
        if request.status_code == 200:
            self._state = False
        else:
            _LOGGER.error("Can't turn off %s. Is resource/endpoint offline?",
                          self._resource)

    def update(self):
        """Get the latest data from REST API and update the state."""
        request = requests.get(self._resource, timeout=10)
        if request.text == self._body_on:
            self._state = True
        elif request.text == self._body_off:
            self._state = False
        else:
            self._state = None
