"""The test for the bayesian sensor platform."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.components.bayesian import binary_sensor as bayesian

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
                    'prob_given_true': 0.6
                }, {
                    'platform': 'numeric_state',
                    'entity_id': 'sensor.test_monitored1',
                    'below': 7,
                    'above': 5,
                    'prob_given_true': 0.9,
                    'prob_given_false': 0.1
                }],
                'prior':
                0.2,
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 4)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')

        assert [] == state.attributes.get('observations')
        assert 0.2 == state.attributes.get('probability')

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 6)
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 4)
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 6)
        self.hass.states.set('sensor.test_monitored1', 6)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')
        assert [{
            'prob_false': 0.4,
            'prob_true': 0.6
        }, {
            'prob_false': 0.1,
            'prob_true': 0.9
        }] == state.attributes.get('observations')
        assert round(abs(0.77-state.attributes.get('probability')), 7) == 0

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 6)
        self.hass.states.set('sensor.test_monitored1', 0)
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 4)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')
        assert 0.2 == state.attributes.get('probability')

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
                    'prob_given_true': 0.8,
                    'prob_given_false': 0.4
                }],
                'prior':
                0.2,
                'probability_threshold':
                0.32,
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 'on')

        state = self.hass.states.get('binary_sensor.test_binary')

        assert [] == state.attributes.get('observations')
        assert 0.2 == state.attributes.get('probability')

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 'off')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 'on')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 'off')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')
        assert [{
            'prob_true': 0.8,
            'prob_false': 0.4
        }] == state.attributes.get('observations')
        assert round(abs(0.33-state.attributes.get('probability')), 7) == 0

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 'off')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 'on')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')
        assert round(abs(0.2-state.attributes.get('probability')), 7) == 0

        assert state.state == 'off'

    def test_threshold(self):
        """Test sensor on probabilty threshold limits."""
        config = {
            'binary_sensor': {
                'name':
                'Test_Binary',
                'platform':
                'bayesian',
                'observations': [{
                    'platform': 'state',
                    'entity_id': 'sensor.test_monitored',
                    'to_state': 'on',
                    'prob_given_true': 1.0,
                }],
                'prior':
                0.5,
                'probability_threshold':
                1.0,
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 'on')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')
        assert round(abs(1.0-state.attributes.get('probability')), 7) == 0

        assert state.state == 'on'

    def test_multiple_observations(self):
        """Test sensor with multiple observations of same entity."""
        config = {
            'binary_sensor': {
                'name':
                'Test_Binary',
                'platform':
                'bayesian',
                'observations': [{
                    'platform': 'state',
                    'entity_id': 'sensor.test_monitored',
                    'to_state': 'blue',
                    'prob_given_true': 0.8,
                    'prob_given_false': 0.4
                }, {
                    'platform': 'state',
                    'entity_id': 'sensor.test_monitored',
                    'to_state': 'red',
                    'prob_given_true': 0.2,
                    'prob_given_false': 0.4
                }],
                'prior':
                0.2,
                'probability_threshold':
                0.32,
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 'off')

        state = self.hass.states.get('binary_sensor.test_binary')

        assert [] == state.attributes.get('observations')
        assert 0.2 == state.attributes.get('probability')

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 'blue')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 'off')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 'blue')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')
        assert [{
            'prob_true': 0.8,
            'prob_false': 0.4
        }] == state.attributes.get('observations')
        assert round(abs(0.33-state.attributes.get('probability')), 7) == 0

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 'blue')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_monitored', 'red')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_binary')
        assert round(abs(0.11-state.attributes.get('probability')), 7) == 0

        assert state.state == 'off'

    def test_probability_updates(self):
        """Test probability update function."""
        prob_true = [0.3, 0.6, 0.8]
        prob_false = [0.7, 0.4, 0.2]
        prior = 0.5

        for pt, pf in zip(prob_true, prob_false):
            prior = bayesian.update_probability(prior, pt, pf)

        assert round(abs(0.720000-prior), 7) == 0

        prob_true = [0.8, 0.3, 0.9]
        prob_false = [0.6, 0.4, 0.2]
        prior = 0.7

        for pt, pf in zip(prob_true, prob_false):
            prior = bayesian.update_probability(prior, pt, pf)

        assert round(abs(0.9130434782608695-prior), 7) == 0
