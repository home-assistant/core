"""The test for the Range sensor platform."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.const import (
        ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN, TEMP_CELSIUS)

from tests.common import get_test_home_assistant


class TestRangeSensor(unittest.TestCase):
    """Test the Range sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_sensor_in_range_no_hysteresis(self):
        """Test if source is within the range."""
        config = {
            'binary_sensor': {
                'platform': 'range',
                'value_lower': '10',
                'value_upper': '20',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('sensor.test_monitored',
                         state.attributes.get('entity_id'))
        self.assertEqual(16, state.attributes.get('sensor_value'))
        self.assertEqual('in range', state.attributes.get('position'))
        self.assertEqual(float(config['binary_sensor']['value_lower']),
                         state.attributes.get('value_lower'))
        self.assertEqual(float(config['binary_sensor']['value_upper']),
                         state.attributes.get('value_upper'))
        self.assertEqual(0.0, state.attributes.get('hysteresis'))

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 9)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('below', state.attributes.get('position'))
        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 21)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('above', state.attributes.get('position'))
        assert state.state == 'off'

    def test_sensor_in_range_with_hysteresis(self):
        """Test if source is within the range."""
        config = {
            'binary_sensor': {
                'platform': 'range',
                'value_lower': '10',
                'value_upper': '20',
                'hysteresis': '2',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('sensor.test_monitored',
                         state.attributes.get('entity_id'))
        self.assertEqual(16, state.attributes.get('sensor_value'))
        self.assertEqual('in range', state.attributes.get('position'))
        self.assertEqual(float(config['binary_sensor']['value_lower']),
                         state.attributes.get('value_lower'))
        self.assertEqual(float(config['binary_sensor']['value_upper']),
                         state.attributes.get('value_upper'))
        self.assertEqual(float(config['binary_sensor']['hysteresis']),
                         state.attributes.get('hysteresis'))

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 8)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('in range', state.attributes.get('position'))
        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 7)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('below', state.attributes.get('position'))
        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 12)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('below', state.attributes.get('position'))
        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 13)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('in range', state.attributes.get('position'))
        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 22)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('in range', state.attributes.get('position'))
        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 23)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('above', state.attributes.get('position'))
        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 18)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('above', state.attributes.get('position'))
        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 17)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('in range', state.attributes.get('position'))
        assert state.state == 'on'

    def test_sensor_in_range_unknown_state(self):
        """Test if source is within the range."""
        config = {
            'binary_sensor': {
                'platform': 'range',
                'value_lower': '10',
                'value_upper': '20',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('sensor.test_monitored',
                         state.attributes.get('entity_id'))
        self.assertEqual(16, state.attributes.get('sensor_value'))
        self.assertEqual('in range', state.attributes.get('position'))
        self.assertEqual(float(config['binary_sensor']['value_lower']),
                         state.attributes.get('value_lower'))
        self.assertEqual(float(config['binary_sensor']['value_upper']),
                         state.attributes.get('value_upper'))
        self.assertEqual(0.0, state.attributes.get('hysteresis'))

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', STATE_UNKNOWN)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.range')

        self.assertEqual('sensor value unknown',
                         state.attributes.get('position'))
        assert state.state == 'off'
