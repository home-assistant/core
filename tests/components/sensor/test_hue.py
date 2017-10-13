"""The tests for the hue sensors platform."""

import json
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component
from tests.common import (
    get_test_home_assistant, load_fixture)

DOMAIN = 'hue'
VALID_CONFIG = {
    'platform': 'hue'
}


class TestHueSensor(unittest.TestCase):
    """Test the Hue-sensors platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test for operational tube_state sensor with proper attributes."""
        self.assertTrue(
            setup_component(self.hass, 'sensor', {'sensor': VALID_CONFIG}))
        living_room_remote = self.hass.states.get('sensor.living_room_remote')
        assert living_room_remote.name == "Living room remote"
