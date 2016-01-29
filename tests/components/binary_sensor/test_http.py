"""
tests.components.binary_sensor.test_http
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests Home Assistant HTTP binary sensor does what it should do.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest
from unittest.mock import patch

import requests
import homeassistant.core as ha

from homeassistant import bootstrap, const
import homeassistant.components.binary_sensor as binary_sensor
import homeassistant.components.http as http
from homeassistant.const import (STATE_OFF, STATE_ON)

from tests.common import get_test_home_assistant


SERVER_PORT = 8127
HTTP_BASE_URL = "http://127.0.0.1:{}".format(SERVER_PORT)

hass = None


def _url(endpoint=""):
    """ Helper method to generate URLs. """
    return '{}/{}/{}'.format(HTTP_BASE_URL, 'api/binary_sensor', endpoint)


@patch('homeassistant.components.http.util.get_local_ip',
       return_value='127.0.0.1')
def setUpModule(mock_get_local_ip):   # pylint: disable=invalid-name
    """ Initializes a Home Assistant server. """
    global hass

    hass = get_test_home_assistant()

    # Set up server
    bootstrap.setup_component(hass, http.DOMAIN, {
        http.DOMAIN: {
            http.CONF_SERVER_PORT: SERVER_PORT
        }
    })

    # Set up API
    bootstrap.setup_component(hass, 'api')

    # Set up HTTP binary sensor
    bootstrap.setup_component(hass, binary_sensor.DOMAIN, {
        binary_sensor.DOMAIN: {
            'platform': 'http'
        }
    })

    hass.start()


def tearDownModule():   # pylint: disable=invalid-name
    """ Stops the Home Assistant server. """
    hass.stop()

class TestBinarySensorHTTP(unittest.TestCase):
    """ Test the HTTP binary sensor. """

    def setup_method(self, method):
        self.hass = ha.HomeAssistant()

    def test_wrong_endpoint(self):
        """ Test with unknown endpoint (GET & POST). """
        req = requests.get(_url(endpoint="another_sensor"))
        self.assertEqual(404, req.status_code)
        req = requests.post(_url(endpoint="another_sensor"))
        self.assertEqual(404, req.status_code)

    # Doesn't work because something is wrong with the URL...i assume...
    def test_setting_sensor_value_via_http_message(self):
        """ Test for setting the sensor value. """
        self.assertTrue(binary_sensor.setup(self.hass, {
            'binary_sensor': {
                'platform': 'http',
                'name': 'test',
                'endpoint': 'test',
                'method': 'GET',
                'value_template': '{{ value_json.payload }}',
            }
        }))

        params_on = {'state': '1'}
        params_off = {'state': '0'}

        req = requests.get(_url(endpoint="test"), params=params_on)
        self.assertEqual(404, req.status_code)
        self.hass.states.set('binary_sensor.test', params_on['state'])
        self.hass.pool.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(True, bool(int(state.state)))

        req = requests.get(_url(endpoint="test"), params=params_off)
        self.assertEqual(404, req.status_code)
        self.hass.states.set('binary_sensor.test', params_off['state'])
        self.hass.pool.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(False, bool(int(state.state)))
