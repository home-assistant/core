"""The tests for the tube_state platform."""
import unittest
import requests_mock

from homeassistant.components.sensor import tube_state
from homeassistant.components.sensor.tube_state import CONF_LINE, URL
from homeassistant.setup import setup_component
from tests.common import load_fixture, get_test_home_assistant


class TestLondonTubeSensor(unittest.TestCase):
    """Test the tube_state platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = {CONF_LINE: ['London Overground']}

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock_req):
        """Test for operational tube_state sensor with proper attributes."""
        mock_req.get(URL, text=load_fixture('tube_state.json'))
        self.assertTrue(
            setup_component(self.hass, 'sensor', {'tube_state': self.config}))

        ids = self.hass.states.entity_ids()
        assert len(ids) > 0
        state = self.hass.states.get('sensor.london_overground')
        assert state.state == 'Minor Delays'
        assert state.attributes.get('Description') == 'something'
