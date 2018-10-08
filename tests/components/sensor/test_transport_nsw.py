"""The tests for the Transport NSW (AU) sensor platform."""
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

VALID_CONFIG = {'sensor': {
    'platform': 'transport_nsw',
    'stopid': '209516',
    'route':  '199',
    'apikey': 'YOUR_API_KEY'}
    }


def get_departuresMock(_stop_id, route, api_key):
    """Mock TransportNSW departures loading."""
    data = {
        'stopid': '209516',
        'route': '199',
        'due': 16,
        'delay': 6,
        'realtime': 'y'
        }
    return data


class TestRMVtransportSensor(unittest.TestCase):
    """Test the TransportNSW sensor."""

    def setUp(self):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG
        self.reference = {}
        self.entities = []

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('TransportNSW.TransportNSW.get_departures',
           side_effect=get_departuresMock)
    def test_transportnsw_config(self, mock_get_departures):
        """Test minimal TransportNSW configuration."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG)
        state = self.hass.states.get('sensor.manly_bus')
        self.assertEqual(state.state, 16)
        self.assertEqual(state.attributes['stopid'], '209516')
        self.assertEqual(state.attributes['route'], '199')
        self.assertEqual(state.attributes['delay'], 6)
        self.assertEqual(state.attributes['realtime'], 'n/a')
