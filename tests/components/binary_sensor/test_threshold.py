"""The test for the threshold sensor platform."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.const import (
        ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN, TEMP_CELSIUS)

from tests.common import get_test_home_assistant


class TestThresholdSensor(unittest.TestCase):
    """Test the threshold sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_sensor_upper(self):
        """Test if source is above threshold."""
        config = {
            'binary_sensor': {
                'platform': 'threshold',
                'upper': '15',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('sensor.test_monitored',
                         state.attributes.get('entity_id'))
        self.assertEqual(16, state.attributes.get('sensor_value'))
        self.assertEqual('above', state.attributes.get('position'))
        self.assertEqual(float(config['binary_sensor']['upper']),
                         state.attributes.get('upper'))
        self.assertEqual(0.0, state.attributes.get('hysteresis'))
        self.assertEqual('upper', state.attributes.get('type'))

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 14)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 15)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        assert state.state == 'off'

    def test_sensor_lower(self):
        """Test if source is below threshold."""
        config = {
            'binary_sensor': {
                'platform': 'threshold',
                'lower': '15',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('above', state.attributes.get('position'))
        self.assertEqual(float(config['binary_sensor']['lower']),
                         state.attributes.get('lower'))
        self.assertEqual(0.0, state.attributes.get('hysteresis'))
        self.assertEqual('lower', state.attributes.get('type'))

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 14)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        assert state.state == 'on'

    def test_sensor_hysteresis(self):
        """Test if source is above threshold using hysteresis."""
        config = {
            'binary_sensor': {
                'platform': 'threshold',
                'upper': '15',
                'hysteresis': '2.5',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 20)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('above', state.attributes.get('position'))
        self.assertEqual(float(config['binary_sensor']['upper']),
                         state.attributes.get('upper'))
        self.assertEqual(2.5, state.attributes.get('hysteresis'))
        self.assertEqual('upper', state.attributes.get('type'))

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 13)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 12)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 17)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 18)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        assert state.state == 'on'

    def test_sensor_in_range_no_hysteresis(self):
        """Test if source is within the range."""
        config = {
            'binary_sensor': {
                'platform': 'threshold',
                'lower': '10',
                'upper': '20',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('sensor.test_monitored',
                         state.attributes.get('entity_id'))
        self.assertEqual(16, state.attributes.get('sensor_value'))
        self.assertEqual('in_range', state.attributes.get('position'))
        self.assertEqual(float(config['binary_sensor']['lower']),
                         state.attributes.get('lower'))
        self.assertEqual(float(config['binary_sensor']['upper']),
                         state.attributes.get('upper'))
        self.assertEqual(0.0, state.attributes.get('hysteresis'))
        self.assertEqual('range', state.attributes.get('type'))

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 9)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('below', state.attributes.get('position'))
        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 21)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('above', state.attributes.get('position'))
        assert state.state == 'off'

    def test_sensor_in_range_with_hysteresis(self):
        """Test if source is within the range."""
        config = {
            'binary_sensor': {
                'platform': 'threshold',
                'lower': '10',
                'upper': '20',
                'hysteresis': '2',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('sensor.test_monitored',
                         state.attributes.get('entity_id'))
        self.assertEqual(16, state.attributes.get('sensor_value'))
        self.assertEqual('in_range', state.attributes.get('position'))
        self.assertEqual(float(config['binary_sensor']['lower']),
                         state.attributes.get('lower'))
        self.assertEqual(float(config['binary_sensor']['upper']),
                         state.attributes.get('upper'))
        self.assertEqual(float(config['binary_sensor']['hysteresis']),
                         state.attributes.get('hysteresis'))
        self.assertEqual('range', state.attributes.get('type'))

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 8)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('in_range', state.attributes.get('position'))
        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 7)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('below', state.attributes.get('position'))
        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 12)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('below', state.attributes.get('position'))
        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 13)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('in_range', state.attributes.get('position'))
        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 22)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('in_range', state.attributes.get('position'))
        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 23)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('above', state.attributes.get('position'))
        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 18)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('above', state.attributes.get('position'))
        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 17)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('in_range', state.attributes.get('position'))
        assert state.state == 'on'

    def test_sensor_in_range_unknown_state(self):
        """Test if source is within the range."""
        config = {
            'binary_sensor': {
                'platform': 'threshold',
                'lower': '10',
                'upper': '20',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('sensor.test_monitored',
                         state.attributes.get('entity_id'))
        self.assertEqual(16, state.attributes.get('sensor_value'))
        self.assertEqual('in_range', state.attributes.get('position'))
        self.assertEqual(float(config['binary_sensor']['lower']),
                         state.attributes.get('lower'))
        self.assertEqual(float(config['binary_sensor']['upper']),
                         state.attributes.get('upper'))
        self.assertEqual(0.0, state.attributes.get('hysteresis'))
        self.assertEqual('range', state.attributes.get('type'))

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', STATE_UNKNOWN)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('unknown', state.attributes.get('position'))
        assert state.state == 'off'

    def test_sensor_lower_zero_threshold(self):
        """Test if a lower threshold of zero is set."""
        config = {
            'binary_sensor': {
                'platform': 'threshold',
                'lower': '0',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('lower', state.attributes.get('type'))
        self.assertEqual(float(config['binary_sensor']['lower']),
                         state.attributes.get('lower'))

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', -3)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        assert state.state == 'on'

    def test_sensor_upper_zero_threshold(self):
        """Test if an upper threshold of zero is set."""
        config = {
            'binary_sensor': {
                'platform': 'threshold',
                'upper': '0',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', -10)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('upper', state.attributes.get('type'))
        self.assertEqual(float(config['binary_sensor']['upper']),
                         state.attributes.get('upper'))

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 2)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        assert state.state == 'on'
