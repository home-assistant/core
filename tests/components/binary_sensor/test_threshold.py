"""The test for the threshold sensor platform."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.const import (ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS)

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
                'threshold': '15',
                'type': 'upper',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('upper', state.attributes.get('type'))
        self.assertEqual('sensor.test_monitored',
                         state.attributes.get('entity_id'))
        self.assertEqual(16, state.attributes.get('sensor_value'))
        self.assertEqual(float(config['binary_sensor']['threshold']),
                         state.attributes.get('threshold'))

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
                'threshold': '15',
                'name': 'Test_threshold',
                'type': 'lower',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_threshold')

        self.assertEqual('lower', state.attributes.get('type'))

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 14)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_threshold')

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 15)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_threshold')

        assert state.state == 'off'
