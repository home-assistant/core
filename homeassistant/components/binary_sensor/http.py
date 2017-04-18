"""
homeassistant.components.binary_sensor.http
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The http binary sensor will consume value sent through the Home Assistant API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.http/

Configuration sample:
  - platform: http
    name: Radio

To test it:

$ curl -X POST -H "x-ha-access: YOUR_PASSWORD" \
    -d '{"state": "on", "attributes": {"friendly_name": "Radio"}}' \
    http://localhost:8123/api/states/binary_sensor.radio

$ curl -X POST -H "x-ha-access: YOUR_PASSWORD" \
    -d '{"state": "off", "attributes": {"friendly_name": "Radio"}}' \
    http://localhost:8123/api/states/binary_sensor.radio
"""
import logging

from homeassistant.components.binary_sensor import (BinarySensorDevice, DOMAIN)
from homeassistant.util import slugify
from homeassistant.const import URL_API_STATES

DEPENDENCIES = ['http']
DEFAULT_NAME = 'HTTP Binary Sensor'

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the HTTP binary sensor. """

    if config.get('name') is None:
        _LOGGER.error('Missing required variable: name')
        return False

    name = config.get('name', DEFAULT_NAME)
    entity_id = '{}.{}'.format(DOMAIN, slugify(name.lower()))
    url = '{}/{}'.format(URL_API_STATES, entity_id)

    _LOGGER.info("""
    Binary HTTP sensor '%s' created.
    Send all HTTP POST messages to: %s""", name, url)

    add_devices([HttpBinarySensor(name)])


class HttpBinarySensor(BinarySensorDevice):
    """ Implements a HTTP binary sensor. """

    def __init__(self, name):
        self._name = name
        self._state = False

    @property
    def should_poll(self):
        """ No polling needed. """
        return False

    @property
    def name(self):
        """ The name of the binary sensor. """
        return self._name
