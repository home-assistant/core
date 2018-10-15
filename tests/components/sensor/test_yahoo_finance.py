"""The tests for the Yahoo Finance platform."""
import json

import unittest
from unittest.mock import patch

import homeassistant.components.sensor as sensor
from homeassistant.setup import setup_component
from tests.common import (
    get_test_home_assistant, load_fixture, assert_setup_component)

VALID_CONFIG = {
    'platform': 'yahoo_finance',
    'symbols': [
        'YHOO',
    ]
}


# pylint: disable=invalid-name
class TestYahooFinanceSetup(unittest.TestCase):
    """Test the Yahoo Finance platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('yahoo_finance.Base._request',
           return_value=json.loads(load_fixture('yahoo_finance.json')))
    def test_default_setup(self, mock_request):
        """Test the default setup."""
        with assert_setup_component(1, sensor.DOMAIN):
            assert setup_component(self.hass, sensor.DOMAIN, {
                'sensor': VALID_CONFIG})

        state = self.hass.states.get('sensor.yhoo')
        self.assertEqual('41.69', state.attributes.get('open'))
        self.assertEqual('41.79', state.attributes.get('prev_close'))
        self.assertEqual('YHOO', state.attributes.get('unit_of_measurement'))
