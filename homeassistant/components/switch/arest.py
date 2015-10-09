"""
homeassistant.components.switch.arest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The arest switch can control the digital pins of a device running with the
aREST RESTful framework for Arduino, the ESP8266, and the Raspberry Pi.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.arest.html
"""
import logging
from requests import get, exceptions

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import DEVICE_DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the aREST switches. """

    resource = config.get('resource', None)

    try:
        response = get(resource, timeout=10)
    except exceptions.MissingSchema:
        _LOGGER.error("Missing resource or schema in configuration. "
                      "Add http:// to your URL.")
        return False
    except exceptions.ConnectionError:
        _LOGGER.error("No route to device. "
                      "Please check the IP address in the configuration file.")
        return False

    dev = []
    pins = config.get('pins')
    for pinnum, pin in pins.items():
        dev.append(ArestSwitch(resource,
                               response.json()['name'],
                               pin.get('name'),
                               pinnum))
    add_devices(dev)


class ArestSwitch(SwitchDevice):
    """ Implements an aREST switch. """

    def __init__(self, resource, location, name, pin):
        self._resource = resource
        self._name = '{} {}'.format(location.title(), name.title()) \
                     or DEVICE_DEFAULT_NAME
        self._pin = pin
        self._state = None

        request = get('{}/mode/{}/o'.format(self._resource, self._pin),
                      timeout=10)
        if request.status_code is not 200:
            _LOGGER.error("Can't set mode. Is device offline?")

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
        request = get('{}/digital/{}/1'.format(self._resource, self._pin),
                      timeout=10)
        if request.status_code == 200:
            self._state = True
        else:
            _LOGGER.error("Can't turn on pin %s at %s. Is device offline?",
                          self._resource, self._pin)

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        request = get('{}/digital/{}/0'.format(self._resource, self._pin),
                      timeout=10)
        if request.status_code == 200:
            self._state = False
        else:
            _LOGGER.error("Can't turn off pin %s at %s. Is device offline?",
                          self._resource, self._pin)

    def update(self):
        """ Gets the latest data from aREST API and updates the state. """
        request = get('{}/digital/{}'.format(self._resource, self._pin),
                      timeout=10)
        self._state = request.json()['return_value'] != 0
