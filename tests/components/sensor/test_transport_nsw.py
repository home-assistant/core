"""The tests for the Transport NSW (AU) sensor platform."""
import unittest

from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

VALID_CONFIG = {'sensor': {
    'platform': 'transport_nsw',
    'stopid': '209516',
    'route':  '199',
    'apikey': 'YOUR_API_KEY'}
    }


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

    def test_transportnsw_config(self):
        """Test minimal TransportNSW configuration."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG)
        state = self.hass.states.get('sensor.manly_bus')
        self.assertEqual(state.state, 'n/a')
        self.assertEqual(state.attributes['stopid'], 'n/a')
        self.assertEqual(state.attributes['route'], 'n/a')
        self.assertEqual(state.attributes['delay'], 'n/a')
        self.assertEqual(state.attributes['realtime'], 'n/a')
