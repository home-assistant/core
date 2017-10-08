"""The tests for the hue sensors platform."""

import requests_mock
import unittest

from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant

DOMAIN = 'hue'
VALID_CONFIG = {
    'platform': 'hue'
}


class TestHueSensor(unittest.TestCase):
    """Test the Hue-sensors platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock_req):
        """Test for operational tube_state sensor with proper attributes."""
        self.assertTrue(
            setup_component(self.hass, 'sensor', {'sensor': self.config}))
