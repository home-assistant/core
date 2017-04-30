"""Unit tests for platform/plant.py."""

import unittest

from tests.common import get_test_home_assistant
import homeassistant.components.plant as plant


class TestPlant(unittest.TestCase):
    """test the processing of data."""

    GOOD_DATA = {
        'moisture': 50,
        'battery': 90,
        'temperature': 23.4,
        'conductivity': 777,
        'brightness': 987,
    }

    GOOD_CONFIG = {
        'sensors': {
            'moisture': 'sensor.mqtt_plant_moisture',
            'battery': 'sensor.mqtt_plant_battery',
            'temperature': 'sensor.mqtt_plant_temperature',
            'conductivity': 'sensor.mqtt_plant_conductivity',
            'brightness': 'sensor.mqtt_plant_brightness',
        },
        'min_moisture': 20,
        'max_moisture': 60,
        'min_battery': 17,
        'min_conductivity': 500,
        'min_temperature': 15,
    }

    class _MockState(object):

        def __init__(self, state=None):
            self.state = state

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_valid_data(self):
        """Test processing valid data."""
        self.sensor = plant.Plant('my plant', self.GOOD_CONFIG)
        self.sensor.hass = self.hass
        for reading, value in self.GOOD_DATA.items():
            self.sensor.state_changed(
                self.GOOD_CONFIG['sensors'][reading], None,
                TestPlant._MockState(value))
        self.assertEqual(self.sensor.state, 'ok')
        attrib = self.sensor.state_attributes
        for reading, value in self.GOOD_DATA.items():
            # battery level has a different name in
            # the JSON format than in hass
            self.assertEqual(attrib[reading], value)

    def test_low_battery(self):
        """Test processing with low battery data and limit set."""
        self.sensor = plant.Plant(self.hass, self.GOOD_CONFIG)
        self.sensor.hass = self.hass
        self.assertEqual(self.sensor.state_attributes['problem'], 'none')
        self.sensor.state_changed('sensor.mqtt_plant_battery',
                                  TestPlant._MockState(45),
                                  TestPlant._MockState(10))
        self.assertEqual(self.sensor.state, 'problem')
        self.assertEqual(self.sensor.state_attributes['problem'],
                         'battery low')
