"""The tests for the Foobot sensor platform."""

import re
import sys
import unittest

import homeassistant.components.sensor as sensor
from homeassistant.setup import setup_component
from homeassistant.const import (TEMP_CELSIUS)
from tests.common import (
    get_test_home_assistant, load_fixture, assert_setup_component)

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

    @unittest.skipIf(sys.version_info < (3, 5),
                     "Test not working on Python 3.4")
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

            state = self.hass.states.get('sensor.foobot_happybot_co2')
            self.assertEqual('1232.0', state.state)
            self.assertEqual('ppm',
                             state.attributes.get('unit_of_measurement'))

            state = self.hass.states.get('sensor.foobot_happybot_temperature')
            self.assertEqual('21.1', state.state)
            self.assertEqual(TEMP_CELSIUS,
                             state.attributes.get('unit_of_measurement'))

            state = self.hass.states.get('sensor.foobot_happybot_humidity')
            self.assertEqual('49.5', state.state)
            self.assertEqual('%', state.attributes.get('unit_of_measurement'))

            state = self.hass.states.get('sensor.foobot_happybot_pm25')
            self.assertEqual('144.8', state.state)
            self.assertEqual('µg/m3',
                             state.attributes.get('unit_of_measurement'))

            state = self.hass.states.get('sensor.foobot_happybot_voc')
            self.assertEqual('340.7', state.state)
            self.assertEqual('ppb',
                             state.attributes.get('unit_of_measurement'))

            state = self.hass.states.get('sensor.foobot_happybot_index')
            self.assertEqual('138.9', state.state)
            self.assertEqual('%',
                             state.attributes.get('unit_of_measurement'))
