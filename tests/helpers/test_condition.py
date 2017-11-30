"""Test the condition helper."""
from unittest.mock import patch

from homeassistant.helpers import condition
from homeassistant.util import dt

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

    def test_and_condition_with_template(self):
        """Test the 'and' condition."""
        test = condition.from_config({
            'condition': 'and',
            'conditions': [
                {
                    'condition': 'template',
                    'value_template':
                    '{{ states.sensor.temperature.state == "100" }}',
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

    def test_or_condition_with_template(self):
        """Test the 'or' condition."""
        test = condition.from_config({
            'condition': 'or',
            'conditions': [
                {
                    'condition': 'template',
                    'value_template':
                    '{{ states.sensor.temperature.state == "100" }}',
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

    def test_time_window(self):
        """Test time condition windows."""
        sixam = dt.parse_time("06:00:00")
        sixpm = dt.parse_time("18:00:00")

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=dt.now().replace(hour=3)):
            assert not condition.time(after=sixam, before=sixpm)
            assert condition.time(after=sixpm, before=sixam)

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=dt.now().replace(hour=9)):
            assert condition.time(after=sixam, before=sixpm)
            assert not condition.time(after=sixpm, before=sixam)

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=dt.now().replace(hour=15)):
            assert condition.time(after=sixam, before=sixpm)
            assert not condition.time(after=sixpm, before=sixam)

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=dt.now().replace(hour=21)):
            assert not condition.time(after=sixam, before=sixpm)
            assert condition.time(after=sixpm, before=sixam)
