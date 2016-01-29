"""
homeassistant.components.binary_sensor.http
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The http binary sensor will consume value sent by a Home Assistant endpoint.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.http/

Configuration sample:
  - platform: http
    endpoint: radio
    method: GET or POST
    name: Radio
    payload_on: "1"
    payload_off: "0"
    value_template: '{{ value_json.payload }}'

To test it:
curl -X GET -H "x-ha-access: mypass" \
    -d '{"payload": "1"}' \
    http://localhost:8123/api/binary_sensor/radio
curl -X POST -d '{"payload": "1"}' \
    http://localhost:8123/api/binary_sensor/radio
curl -X POST http://127.0.0.1:8123/api/binary_sensor/radio?payload=1
"""
import logging
import json
from functools import partial

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import (CONF_VALUE_TEMPLATE,
                                 HTTP_INTERNAL_SERVER_ERROR,
                                 HTTP_UNPROCESSABLE_ENTITY)
from homeassistant.util import template

DEPENDENCIES = ['http']
URL_API_BINARY_SENSOR_ENDPOINT = '/api/binary_sensor'
DEFAULT_NAME = 'HTTP Binary Sensor'
DEFAULT_METHOD = 'GET'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the HTTP binary sensor. """

    if config.get('endpoint') is None:
        _LOGGER.error('Missing required variable: endpoint')
        return False

    method = config.get('method', DEFAULT_METHOD)
    endpoint = '{}/{}'.format(URL_API_BINARY_SENSOR_ENDPOINT,
                              config.get('endpoint'))

    add_devices(
        [HttpBinarySensor(hass,
                          endpoint,
                          method,
                          config.get('name', DEFAULT_NAME),
                          config.get('payload_on', DEFAULT_PAYLOAD_ON),
                          config.get('payload_off', DEFAULT_PAYLOAD_OFF),
                          config.get(CONF_VALUE_TEMPLATE))])


# pylint: disable=too-many-arguments
class HttpBinarySensor(BinarySensorDevice):
    """ Implements a HTTP binary sensor. """

    def __init__(self, hass, endpoint, method, name, payload_on,
                 payload_off, value_template):
        self._endpoint = endpoint
        self._method = method
        self._name = name
        self._state = False
        self._payload_on = payload_on
        self._payload_off = payload_off

        def _handle_get_api_binary_sensor(hass, handler, path_match, data):
            """ Message for binary sensor received. """

            if not isinstance(data, dict):
                handler.write_json_message(
                    "Error while parsing HTTP message",
                    HTTP_INTERNAL_SERVER_ERROR)
                return

            if value_template is not None:
                data = template.render_with_possible_json_value(
                    hass, value_template, json.dumps(data))

            if not data:
                handler.write_json_message("Key unknown.",
                                           HTTP_UNPROCESSABLE_ENTITY)
                _LOGGER.error("Key unknown")
                return

            if data == self._payload_on:
                self._state = True
            elif data == self._payload_off:
                self._state = False
            else:
                self._state = bool(int(data))

            handler.write_json_message("Binary sensor value processed.")
            self.update_ha_state()

        if self._method == 'GET':
            hass.http.register_path(
                'GET', endpoint, partial(_handle_get_api_binary_sensor, hass))
        elif self._method == 'POST':
            hass.http.register_path(
                'POST', endpoint, partial(_handle_get_api_binary_sensor, hass))

    @property
    def name(self):
        """ The name of the binary sensor. """
        return self._name

    @property
    def is_on(self):
        """ True if the binary sensor is on. """
        return self._state
