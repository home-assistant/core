"""The tests for the Open Hardware Monitor platform."""
import unittest
import requests_mock
from homeassistant.components.sensor import openhardwaremonitor
from homeassistant.setup import setup_component

from tests.common import load_fixture, get_test_home_assistant


class TestOpenHardwareMonitorSetup(unittest.TestCase):
    """Test the Open Hardware Monitor platform."""

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
        self.config = {
            'host': 'localhost',
            'port': 8085
        }
        self.entities = []

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_with_config(self):
        """Test the platform setup with configuration."""
        self.assertTrue(
            setup_component(self.hass, 'sensor', {
                'openhardwaremonitor': self.config}))

    @requests_mock.Mocker()
    def test_setup(self, mock_req):
        """Test for successfully setting up the platform."""
        mock_req.get('/data.json',
                     text=load_fixture('openhardwaremonitor.json'))
        openhardwaremonitor.setup_platform(
            self.hass, self.config, self.add_entities)
        self.assertEqual(len(self.entities), 38)
        self.assertEqual(self.entities[0].name,
                         "TEST-PC_Intel Core i7-7700_Clocks_Bus Speed")
        self.assertEqual(self.entities[0].state, '100')
