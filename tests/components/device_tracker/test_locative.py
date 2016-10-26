"""The tests the for Locative device tracker platform."""
import time
import unittest
from unittest.mock import patch

import requests

from homeassistant import bootstrap, const
import homeassistant.components.device_tracker as device_tracker
import homeassistant.components.http as http
from homeassistant.const import CONF_PLATFORM

from tests.common import get_test_home_assistant, get_test_instance_port

SERVER_PORT = get_test_instance_port()
HTTP_BASE_URL = "http://127.0.0.1:{}".format(SERVER_PORT)

hass = None  # pylint: disable=invalid-name


def _url(data=None):
    """Helper method to generate URLs."""
    data = data or {}
    data = "&".join(["{}={}".format(name, value) for
                     name, value in data.items()])
    return "{}{}locative?{}".format(HTTP_BASE_URL, const.URL_API, data)


def setUpModule():   # pylint: disable=invalid-name
    """Initalize a Home Assistant server."""
    global hass    # pylint: disable=invalid-name

    hass = get_test_home_assistant()
    bootstrap.setup_component(hass, http.DOMAIN, {
        http.DOMAIN: {
            http.CONF_SERVER_PORT: SERVER_PORT
        },
    })

    # Set up device tracker
    bootstrap.setup_component(hass, device_tracker.DOMAIN, {
        device_tracker.DOMAIN: {
            CONF_PLATFORM: 'locative'
        }
    })

    hass.start()
    time.sleep(0.05)


def tearDownModule():   # pylint: disable=invalid-name
    """Stop the Home Assistant server."""
    hass.stop()


# Stub out update_config or else Travis CI raises an exception
@patch('homeassistant.components.device_tracker.update_config')
class TestLocative(unittest.TestCase):
    """Test Locative platform."""

    def tearDown(self):
        """Stop everything that was started."""
        hass.block_till_done()

    def test_missing_data(self, update_config):
        """Test missing data."""
        data = {
            'latitude': 1.0,
            'longitude': 1.1,
            'device': '123',
            'id': 'Home',
            'trigger': 'enter'
        }

        # No data
        req = requests.get(_url({}))
        self.assertEqual(422, req.status_code)

        # No latitude
        copy = data.copy()
        del copy['latitude']
        req = requests.get(_url(copy))
        self.assertEqual(422, req.status_code)

        # No device
        copy = data.copy()
        del copy['device']
        req = requests.get(_url(copy))
        self.assertEqual(422, req.status_code)

        # No location
        copy = data.copy()
        del copy['id']
        req = requests.get(_url(copy))
        self.assertEqual(422, req.status_code)

        # No trigger
        copy = data.copy()
        del copy['trigger']
        req = requests.get(_url(copy))
        self.assertEqual(422, req.status_code)

        # Test message
        copy = data.copy()
        copy['trigger'] = 'test'
        req = requests.get(_url(copy))
        self.assertEqual(200, req.status_code)

        # Unknown trigger
        copy = data.copy()
        copy['trigger'] = 'foobar'
        req = requests.get(_url(copy))
        self.assertEqual(422, req.status_code)

    def test_enter_and_exit(self, update_config):
        """Test when there is a known zone."""
        data = {
            'latitude': 40.7855,
            'longitude': -111.7367,
            'device': '123',
            'id': 'Home',
            'trigger': 'enter'
        }

        # Enter the Home
        req = requests.get(_url(data))
        self.assertEqual(200, req.status_code)
        state_name = hass.states.get('{}.{}'.format('device_tracker',
                                                    data['device'])).state
        self.assertEqual(state_name, 'home')

        data['id'] = 'HOME'
        data['trigger'] = 'exit'

        # Exit Home
        req = requests.get(_url(data))
        self.assertEqual(200, req.status_code)
        state_name = hass.states.get('{}.{}'.format('device_tracker',
                                                    data['device'])).state
        self.assertEqual(state_name, 'not_home')

        data['id'] = 'hOmE'
        data['trigger'] = 'enter'

        # Enter Home again
        req = requests.get(_url(data))
        self.assertEqual(200, req.status_code)
        state_name = hass.states.get('{}.{}'.format('device_tracker',
                                                    data['device'])).state
        self.assertEqual(state_name, 'home')

        data['trigger'] = 'exit'

        # Exit Home
        req = requests.get(_url(data))
        self.assertEqual(200, req.status_code)
        state_name = hass.states.get('{}.{}'.format('device_tracker',
                                                    data['device'])).state
        self.assertEqual(state_name, 'not_home')

        data['id'] = 'work'
        data['trigger'] = 'enter'

        # Enter Work
        req = requests.get(_url(data))
        self.assertEqual(200, req.status_code)
        state_name = hass.states.get('{}.{}'.format('device_tracker',
                                                    data['device'])).state
        self.assertEqual(state_name, 'work')

    def test_exit_after_enter(self, update_config):
        """Test when an exit message comes after an enter message."""
        data = {
            'latitude': 40.7855,
            'longitude': -111.7367,
            'device': '123',
            'id': 'Home',
            'trigger': 'enter'
        }

        # Enter Home
        req = requests.get(_url(data))
        self.assertEqual(200, req.status_code)

        state = hass.states.get('{}.{}'.format('device_tracker',
                                               data['device']))
        self.assertEqual(state.state, 'home')

        data['id'] = 'Work'

        # Enter Work
        req = requests.get(_url(data))
        self.assertEqual(200, req.status_code)

        state = hass.states.get('{}.{}'.format('device_tracker',
                                               data['device']))
        self.assertEqual(state.state, 'work')

        data['id'] = 'Home'
        data['trigger'] = 'exit'

        # Exit Home
        req = requests.get(_url(data))
        self.assertEqual(200, req.status_code)

        state = hass.states.get('{}.{}'.format('device_tracker',
                                               data['device']))
        self.assertEqual(state.state, 'work')

    def test_exit_first(self, update_config):
        """Test when an exit message is sent first on a new device."""
        data = {
            'latitude': 40.7855,
            'longitude': -111.7367,
            'device': 'new_device',
            'id': 'Home',
            'trigger': 'exit'
        }

        # Exit Home
        req = requests.get(_url(data))
        self.assertEqual(200, req.status_code)

        state = hass.states.get('{}.{}'.format('device_tracker',
                                               data['device']))
        self.assertEqual(state.state, 'not_home')
