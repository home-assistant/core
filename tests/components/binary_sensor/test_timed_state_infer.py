"""The test for the timed state infer binary sensor platform."""
import unittest
from unittest.mock import patch
from datetime import timedelta

from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant, fire_time_changed


class TestTimedStateInferBinarySensor(unittest.TestCase):
    """Test the timed state infer binary sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_sensor_state(self):
        """Test sensor on observed sensor state changes."""
        config = {
            'binary_sensor': {
                'name': 'Test_Sensor',
                'platform': 'timed_state_infer',
                'entity_id': 'input_number.test_monitored',
                'seconds_on': 5,
                'seconds_off': 10,
                'value_on': 5,
                'value_off': 1,
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('input_number.test_monitored', 5)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_sensor')
        assert state.state == 'off'

        # advance the required time for the state to change
        utc_now = dt_util.utcnow() + timedelta(seconds=5)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=utc_now):
            fire_time_changed(self.hass, dt_util.utcnow())
            self.hass.block_till_done()
            state = self.hass.states.get('binary_sensor.test_sensor')
            assert state.state == 'on'

            self.hass.states.set('input_number.test_monitored', 0)
            self.hass.block_till_done()
            assert state.state == 'on'

        utc_now = utc_now + timedelta(seconds=10)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=utc_now):
            fire_time_changed(self.hass, dt_util.utcnow())
            self.hass.block_till_done()
            state = self.hass.states.get('binary_sensor.test_sensor')
            assert state.state == 'off'

        utc_now = utc_now + timedelta(seconds=10)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=utc_now):
            fire_time_changed(self.hass, dt_util.utcnow())
            assert state.state == 'off'
