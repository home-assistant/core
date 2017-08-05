"""The test for the bayesian sensor platform."""
import unittest

from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestBayesianBinarySensor(unittest.TestCase):
    """Test the threshold sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_sensor_numeric_state(self):
        """Test sensor on numeric state platform observations."""
        config = {
            'binary_sensor': {
                'platform':
                'bayesian',
                'name':
                'Test_Binary',
                'observations': [{
                    'platform': 'numeric_state',
                    'entity_id': 'sensor.test_monitored',
                    'below': 10,
                    'above': 5,
                    'probability': 0.8
                }],
                'prior':
                0.2,
                'probability_threshold':
                0.4,
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 4)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')

        self.assertEqual([], state.attributes.get('observations'))
        self.assertEqual(0.2, state.attributes.get('probability'))

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 6)
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 4)
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 6)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')
        self.assertEqual([0.8], state.attributes.get('observations'))
        self.assertAlmostEqual(0.5, state.attributes.get('probability'))

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 6)
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 4)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')
        self.assertAlmostEqual(0.2, state.attributes.get('probability'))

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 15)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')

        assert state.state == 'off'

    def test_sensor_state(self):
        """Test sensor on state platform observations."""
        config = {
            'binary_sensor': {
                'name':
                'Test_Binary',
                'platform':
                'bayesian',
                'observations': [{
                    'platform': 'state',
                    'entity_id': 'sensor.test_monitored',
                    'to_state': 'off',
                    'probability': 0.8
                }],
                'prior':
                0.2,
                'probability_threshold':
                0.4,
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 'on')

        state = self.hass.states.get('binary_sensor.test_binary')

        self.assertEqual([], state.attributes.get('observations'))
        self.assertEqual(0.2, state.attributes.get('probability'))

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 'off')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 'on')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 'off')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')
        self.assertEqual([0.8], state.attributes.get('observations'))
        self.assertAlmostEqual(0.5, state.attributes.get('probability'))

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 'off')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 'on')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')
        self.assertAlmostEqual(0.2, state.attributes.get('probability'))

        assert state.state == 'off'
