"""The tests for the tube_state platform."""
import unittest
import requests_mock

from homeassistant.components.sensor import tube_state
from homeassistant.components.sensor.tube_state import CONF_LINE
from homeassistant.setup import setup_component
from tests.common import load_fixture, get_test_home_assistant


class TestLondonTubeSensor(unittest.TestCase):
    """Test the tube_state platform."""

    def add_entities(self, new_entities, update_before_add=False):
        """Mock add entities."""
        if update_before_add:
            for entity in new_entities:
                entity.update()

        for entity in new_entities:
            self.entities.append(entity)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = {CONF_LINE: ['London Overground']}
        self.entities = []

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_with_config(self):
        """Test the platform setup with configuration."""
        self.assertTrue(
            setup_component(self.hass, 'sensor', {'tube_state': self.config}))

    @requests_mock.Mocker()
    def test_setup(self, mock_req):
        """Test for operational WSDOT sensor with proper attributes."""
        url = 'https://api.tfl.gov.uk/line/mode/tube,overground,dlr,tflrail/status'
        mock_req.get(url, text=load_fixture('tube_state.json'))
        tube_state.setup_platform(self.hass, self.config, self.add_entities)
        self.assertEqual(len(self.entities), 1)
        sensor = self.entities[0]
        self.assertEqual(sensor.name, 'London Overground')
        self.assertEqual(sensor.state, 'Minor Delays')
