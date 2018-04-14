"""The test for the data filter sensor platform."""
from datetime import timedelta
import unittest
from unittest.mock import patch

from homeassistant.components.sensor.filter import (
    LowPassFilter, OutlierFilter, ThrottleFilter, TimeSMAFilter)
import homeassistant.util.dt as dt_util
from homeassistant.setup import setup_component
import homeassistant.core as ha
from tests.common import (get_test_home_assistant, assert_setup_component,
                          init_recorder_component)


class TestFilterSensor(unittest.TestCase):
    """Test the Data Filter sensor."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        raw_values = [20, 19, 18, 21, 22, 0]
        self.values = []

        timestamp = dt_util.utcnow()
        for val in raw_values:
            self.values.append(ha.State('sensor.test_monitored',
                                        val, last_updated=timestamp))
            timestamp += timedelta(minutes=1)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def init_recorder(self):
        """Initialize the recorder."""
        init_recorder_component(self.hass)
        self.hass.start()

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
        self.init_recorder()
        config = {
            'history': {
            },
            'sensor': {
                'platform': 'filter',
                'name': 'test',
                'entity_id': 'sensor.test_monitored',
                'history_period': '00:05',
                'filters': [{
                    'filter': 'outlier',
                    'window_size': 10,
                    'radius': 4.0
                    }, {
                        'filter': 'lowpass',
                        'time_constant': 10,
                        'precision': 2
                    }]
            }
        }
        t_0 = dt_util.utcnow() - timedelta(minutes=1)
        t_1 = dt_util.utcnow() - timedelta(minutes=2)
        t_2 = dt_util.utcnow() - timedelta(minutes=3)

        fake_states = {
            'sensor.test_monitored': [
                ha.State('sensor.test_monitored', 18.0, last_changed=t_0),
                ha.State('sensor.test_monitored', 19.0, last_changed=t_1),
                ha.State('sensor.test_monitored', 18.2, last_changed=t_2),
            ]
        }

        with patch('homeassistant.components.history.'
                   'state_changes_during_period', return_value=fake_states):
            with patch('homeassistant.components.history.'
                       'get_last_state_changes', return_value=fake_states):
                with assert_setup_component(1, 'sensor'):
                    assert setup_component(self.hass, 'sensor', config)

                for value in self.values:
                    self.hass.states.set(
                        config['sensor']['entity_id'], value.state)
                    self.hass.block_till_done()

                state = self.hass.states.get('sensor.test')
                self.assertEqual('17.05', state.state)

    def test_outlier(self):
        """Test if outlier filter works."""
        filt = OutlierFilter(window_size=3,
                             precision=2,
                             entity=None,
                             radius=4.0)
        for state in self.values:
            filtered = filt.filter_state(state)
        self.assertEqual(22, filtered.state)

    def test_initial_outlier(self):
        """Test issue #13363."""
        filt = OutlierFilter(window_size=3,
                             precision=2,
                             entity=None,
                             radius=4.0)
        out = ha.State('sensor.test_monitored', 4000)
        for state in [out]+self.values:
            filtered = filt.filter_state(state)
        self.assertEqual(22, filtered.state)

    def test_lowpass(self):
        """Test if lowpass filter works."""
        filt = LowPassFilter(window_size=10,
                             precision=2,
                             entity=None,
                             time_constant=10)
        for state in self.values:
            filtered = filt.filter_state(state)
        self.assertEqual(18.05, filtered.state)

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
        self.assertEqual([20, 21], [f.state for f in filtered])

    def test_time_sma(self):
        """Test if time_sma filter works."""
        filt = TimeSMAFilter(window_size=timedelta(minutes=2),
                             precision=2,
                             entity=None,
                             type='last')
        for state in self.values:
            filtered = filt.filter_state(state)
        self.assertEqual(21.5, filtered.state)
