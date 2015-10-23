# -*- coding: utf-8 -*-
"""
homeassistant.components.switch.rest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a REST switch.

Configuration:

switch:
  platform: rest
  name: "Bedroom Switch"
  resource: "http://IP_ADDRESS/ENDPOINT"
  body_on: "ON"
  body_off: "OFF"

Variables:

resource
*Required*

name
*Optional
The name of the switch. Default is 'REST Switch'.

body_on
*Optional
The body that represents enabled state. Default is "ON".

body_off
*Optional
The body that represents disabled state. Default is "OFF".

"""

import logging
import requests

from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "REST Switch"
DEFAULT_BODY_ON = "ON"
DEFAULT_BODY_OFF = "OFF"


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add REST Switch """

    resource = config.get('resource')

    if resource is None:
        _LOGGER.error("Missing required variable: resource")
        return False

    try:
        requests.get(resource, timeout=10)
    except requests.exceptions.MissingSchema:
        _LOGGER.error("Missing resource or schema in configuration. "
                      "Add http:// to your URL.")
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to device. "
                      "Please check the IP address in the configuration file.")
        return False

    add_devices_callback([RestSwitch(
        hass,
        config.get('name', DEFAULT_NAME),
        config.get('resource'),
        config.get('body_on', DEFAULT_BODY_ON),
        config.get('body_off', DEFAULT_BODY_OFF))])


# pylint: disable=too-many-arguments
class RestSwitch(SwitchDevice):
    """ Represents a switch that can be togggled using REST """
    def __init__(self, hass, name, resource, body_on, body_off):
        self._state = None
        self._hass = hass
        self._name = name
        self._resource = resource
        self._body_on = body_on
        self._body_off = body_off

    @property
    def name(self):
        """ The name of the switch. """
        return self._name

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        request = requests.post(self._resource,
                                data=self._body_on,
                                timeout=10)
        if request.status_code == 200:
            self._state = True
        else:
            _LOGGER.error("Can't turn on %s. Is device offline?",
                          self._resource)

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        request = requests.post(self._resource,
                                data=self._body_off,
                                timeout=10)
        if request.status_code == 200:
            self._state = False
        else:
            _LOGGER.error("Can't turn off %s. Is device offline?",
                          self._resource)

    def update(self):
        """ Gets the latest data from REST API and updates the state. """
        request = requests.get(self._resource, timeout=10)
        if request.text == self._body_on:
            self._state = True
        elif request.text == self._body_off:
            self._state = False
        else:
            self._state = None
