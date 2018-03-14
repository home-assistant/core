"""The tests for the Foobot sensor platform."""

import re
import unittest

import homeassistant.components.sensor as sensor
from homeassistant.const import (TEMP_CELSIUS)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.setup import setup_component
from tests.common import (
    assert_setup_component, get_test_home_assistant, load_fixture)

from ...test_util.aiohttp import mock_aiohttp_client

VALID_CONFIG = {
    'platform': 'foobot',
    'token': 'adfdsfasd',
    'username': 'example@example.com',
}


# pylint: disable=invalid-name
class TestFoobotSetup(unittest.TestCase):
    """Test the setup portion of the Foobot platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_default_setup(self):
        """Test the default setup."""
        with mock_aiohttp_client() as aioclient_mock:
            aioclient_mock.get(re.compile('api.foobot.io/v2/owner/.*'),
                               text=load_fixture('foobot_devices.json'))
            aioclient_mock.get(re.compile('api.foobot.io/v2/device/.*'),
                               text=load_fixture('foobot_data.json'))
            with assert_setup_component(1, sensor.DOMAIN):
                assert setup_component(self.hass, sensor.DOMAIN, {
                    'sensor': VALID_CONFIG})

            metrics = {'co2': ['1232.0', 'ppm'],
                       'temperature': ['21.1', TEMP_CELSIUS],
                       'humidity': ['49.5', '%'],
                       'pm25': ['144.8', 'µg/m3'],
                       'voc': ['340.7', 'ppb'],
                       'index': ['138.9', '%']}

            for name, value in metrics.items():
                state = self.hass.states.get('sensor.foobot_happybot_%s'
                                             % name)
                self.assertEqual(value[0], state.state)
                self.assertEqual(value[1],
                                 state.attributes.get('unit_of_measurement'))

    def test_setup_error(self):
        """Expected failures caused by various errors in API response."""
        errors = [[400, None],
                  [401, None],
                  [403, None],
                  [429, PlatformNotReady],
                  [500, PlatformNotReady]]

        for error in errors:
            with mock_aiohttp_client() as aioclient_mock:
                aioclient_mock.get(re.compile('api.foobot.io/v2/owner/.*'),
                                   status=error[0])

                with self.assertRaises(error[1]):
                    yield from setup_component(self.hass, sensor.DOMAIN,
                                               {'sensor': VALID_CONFIG})
