"""Unit tests for sensor/migardener.py."""

import unittest
import unittest.mock as mock

from tests.common import get_test_home_assistant
import homeassistant.components.sensor.migardener as migardener


class TestMiGardener(unittest.TestCase):
    """test the processing of data."""

    GOOD_DATA = {
        'battery': 1,
        'temperature': 2.1,
        'brightness': 3,
        'moisture': 4,
        'conductivity': 5,
    }

    GOOD_CONFIG = {
            'platform': 'migardener',
            'name': 'foo',
            'state_topic': '/some/topic',
    }

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch('homeassistant.components.mqtt.subscribe')
    def test_valid_data(self, _):
        """Test processing valid data."""
        self.sensor = migardener.MiGardener(self.hass, self.GOOD_CONFIG)
        self.sensor._update_state(self.GOOD_DATA)
        self.assertEqual(self.sensor.state, 'ok')
        attrib = self.sensor.state_attributes
        for key, value in self.GOOD_DATA.items():
            # battery level has a different name in
            # the JSON format than in hass
            if key == 'battery':
                key = 'battery_level'
            self.assertEqual(attrib[key], value)

    @mock.patch('homeassistant.components.mqtt.subscribe')
    def test_low_batters(self, _):
        """Test processing with low battery data and limit set."""
        config = self.GOOD_CONFIG.copy()
        config['min_battery'] = 20
        self.sensor = migardener.MiGardener(self.hass, config)
        self.sensor._update_state(self.GOOD_DATA)
        self.assertEqual(self.sensor.state, 'battery low')
