"""The test for the statistics sensor platform."""
import unittest
import statistics

from homeassistant.setup import setup_component
from homeassistant.const import (ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS)
from tests.common import get_test_home_assistant


class TestStatisticsSensor(unittest.TestCase):
    """Test the Statistics sensor."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.values = [17, 20, 15.2, 5, 3.8, 9.2, 6.7, 14, 6]
        self.count = len(self.values)
        self.min = min(self.values)
        self.max = max(self.values)
        self.total = sum(self.values)
        self.mean = round(sum(self.values) / len(self.values), 2)
        self.median = round(statistics.median(self.values), 2)
        self.deviation = round(statistics.stdev(self.values), 2)
        self.variance = round(statistics.variance(self.values), 2)
        self.change = self.values[-1] - self.values[0]
        self.average_change = self.change / (len(self.values) - 1)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_binary_sensor_source(self):
        """Test if source is a sensor."""
        values = [1, 0, 1, 0, 1, 0, 1]
        assert setup_component(self.hass, 'sensor', {
            'sensor': {
                'platform': 'statistics',
                'name': 'test',
                'entity_id': 'binary_sensor.test_monitored',
            }
        })

        for value in values:
            self.hass.states.set('binary_sensor.test_monitored', value)
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_count')

        self.assertEqual(str(len(values)), state.state)

    def test_sensor_source(self):
        """Test if source is a sensor."""
        assert setup_component(self.hass, 'sensor', {
            'sensor': {
                'platform': 'statistics',
                'name': 'test',
                'entity_id': 'sensor.test_monitored',
            }
        })

        for value in self.values:
            self.hass.states.set('sensor.test_monitored', value,
                                 {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_mean')

        self.assertEqual(str(self.mean), state.state)
        self.assertEqual(self.min, state.attributes.get('min_value'))
        self.assertEqual(self.max, state.attributes.get('max_value'))
        self.assertEqual(self.variance, state.attributes.get('variance'))
        self.assertEqual(self.median, state.attributes.get('median'))
        self.assertEqual(self.deviation,
                         state.attributes.get('standard_deviation'))
        self.assertEqual(self.mean, state.attributes.get('mean'))
        self.assertEqual(self.count, state.attributes.get('count'))
        self.assertEqual(self.total, state.attributes.get('total'))
        self.assertEqual('°C', state.attributes.get('unit_of_measurement'))
        self.assertEqual(self.change, state.attributes.get('change'))
        self.assertEqual(self.average_change,
                         state.attributes.get('average_change'))

    def test_sampling_size(self):
        """Test rotation."""
        assert setup_component(self.hass, 'sensor', {
            'sensor': {
                'platform': 'statistics',
                'name': 'test',
                'entity_id': 'sensor.test_monitored',
                'sampling_size': 5,
            }
        })

        for value in self.values:
            self.hass.states.set('sensor.test_monitored', value,
                                 {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_mean')

        self.assertEqual(3.8, state.attributes.get('min_value'))
        self.assertEqual(14, state.attributes.get('max_value'))
