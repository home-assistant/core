"""
tests.components.binary_sensor.test_http
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests HTTP binary sensor.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest
import json
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
API_PASSWORD = "test1234"
HA_HEADERS = {const.HTTP_HEADER_HA_AUTH: API_PASSWORD}
ENTITY_ID = 'binary_sensor.test'

hass = None

def _url(path=""):
    """ Helper method to generate urls. """
    return '{}{}'.format(HTTP_BASE_URL, path)


@patch('homeassistant.components.http.util.get_local_ip',
       return_value='127.0.0.1')
def setUpModule(mock_get_local_ip):   # pylint: disable=invalid-name
    """ Initializes a Home Assistant server. """
    global hass

    hass = get_test_home_assistant()
    hass.states.set(ENTITY_ID, 'off')

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

    def test_sensor(self):
        """ Test for setting the sensor value. """
        self.assertTrue(binary_sensor.setup(hass, {
            'binary_sensor': {
                'platform': 'http',
                'name': 'test',
            }
        }))

        state = hass.states.get(ENTITY_ID)
        self.assertEqual(STATE_OFF, state.state)

        hass.states.set(ENTITY_ID, 'on')
        state = hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_ON, state.state)

        hass.states.set(ENTITY_ID, 'off')
        state = hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_OFF, state.state)

    def test_api_get_state(self):
        """ Test if the sensor allows us to get a state. """
        req = requests.get(
            _url(const.URL_API_STATES_ENTITY.format(ENTITY_ID)),
            headers=HA_HEADERS)

        data = ha.State.from_dict(req.json())
        state = hass.states.get(ENTITY_ID)

        self.assertEqual(state.state, data.state)
        self.assertEqual(state.last_changed, data.last_changed)
        self.assertEqual(state.attributes, data.attributes)

    def test_api_set_state(self):
        """ Test if we can set the state of an binary sensor. """
        hass.states.set(ENTITY_ID, 'not_to_be_set')

        requests.post(_url(const.URL_API_STATES_ENTITY.format(ENTITY_ID)),
                      data=json.dumps({"state": "off"}),
                      headers=HA_HEADERS)

        self.assertEqual("off", hass.states.get(ENTITY_ID).state)

    # pylint: disable=invalid-name
    def test_api_state_change_with_no_data(self):
        """ Test if API sends appropriate error if we omit state. """
        req = requests.post(
            _url(const.URL_API_STATES_ENTITY.format(
                ENTITY_ID)),
            data=json.dumps({}),
            headers=HA_HEADERS)

        self.assertEqual(400, req.status_code)