"""The tests for the hue sensors platform."""

import json
import requests_mock
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component
from tests.common import (
    get_test_home_assistant, load_fixture)

DOMAIN = 'hue'
DUMMY_URL = "http://dummy_url"
VALID_CONFIG = {
    'platform': 'hue'
}


class TestHueSensor(unittest.TestCase):
    """Test the Hue sensors platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock_request):
        """Test for operational tube_state sensor with proper attributes."""
        self.hass.data[DOMAIN] = DUMMY_URL
        mock_request.get(
            DUMMY_URL + '/sensors', text=load_fixture('hue_sensors.json'))

        self.assertTrue(
            setup_component(self.hass, 'sensor', {'sensor': VALID_CONFIG}))
        living_room_remote = self.hass.states.get('sensor.living_room_remote')
        assert living_room_remote.name == "Living room remote"
