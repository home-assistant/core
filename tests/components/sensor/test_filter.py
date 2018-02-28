"""The test for the data filter sensor platform."""
import unittest

from homeassistant.components.sensor.filter import (
    LowPassFilter, OutlierFilter, ThrottleFilter)
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, assert_setup_component


class TestFilterSensor(unittest.TestCase):
    """Test the Data Filter sensor."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.values = [20, 19, 18, 21, 22, 0]

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_fail(self):
        """Test if filter doesn't exist."""
        config = {
            'sensor': {
                'platform': 'filter',
                'entity_id': 'sensor.test_monitored',
                'filters': [{'filter': 'nonexisting'}]
            }
        }
        with assert_setup_component(0):
            assert setup_component(self.hass, 'sensor', config)

    def test_chain(self):
        """Test if filter chaining works."""
        config = {
            'sensor': {
                'platform': 'filter',
                'name': 'test',
                'entity_id': 'sensor.test_monitored',
                'filters': [{
                    'filter': 'outlier',
                    'radius': 4.0
                    }, {
                        'filter': 'lowpass',
                        'window_size': 4,
                        'time_constant': 10,
                        'precision': 2
                    }]
            }
        }
        with assert_setup_component(1):
            assert setup_component(self.hass, 'sensor', config)

        for value in self.values:
            self.hass.states.set(config['sensor']['entity_id'], value)
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.test')
        self.assertEqual('20.25', state.state)

    def test_outlier(self):
        """Test if outlier filter works."""
        filt = OutlierFilter(window_size=10,
                             precision=2,
                             entity=None,
                             radius=4.0)
        for state in self.values:
            filtered = filt.filter_state(state)
        self.assertEqual(22, filtered)

    def test_lowpass(self):
        """Test if lowpass filter works."""
        filt = LowPassFilter(window_size=10,
                             precision=2,
                             entity=None,
                             time_constant=10)
        for state in self.values:
            filtered = filt.filter_state(state)
        self.assertEqual(18.05, filtered)

    def test_throttle(self):
        """Test if lowpass filter works."""
        filt = ThrottleFilter(window_size=3,
                              precision=2,
                              entity=None)
        filtered = []
        for state in self.values:
            new_state = filt.filter_state(state)
            if not filt.skip_processing:
                filtered.append(new_state)
        self.assertEqual([20, 21], filtered)
