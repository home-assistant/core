"""Test the condition helper."""
from homeassistant.helpers import condition

from tests.common import get_test_home_assistant


class TestConditionHelper:
    """Test condition helpers."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_and_condition(self):
        """Test the 'and' condition."""
        test = condition.from_config({
            'condition': 'and',
            'conditions': [
                {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '100',
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 110,
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 120)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 105)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert test(self.hass)

    def test_or_condition(self):
        """Test the 'or' condition."""
        test = condition.from_config({
            'condition': 'or',
            'conditions': [
                {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '100',
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 110,
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 120)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 105)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert test(self.hass)
