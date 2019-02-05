"""Test the condition helper."""
from unittest.mock import patch

from homeassistant.helpers import condition
from homeassistant.util import dt

from tests.common import get_test_home_assistant


class TestConditionHelper:
    """Test condition helpers."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
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

    def test_exor_condition(self):
        """Test the 'exor' condition."""
        test = condition.from_config({
            'condition': 'exor',
            'conditions': [
                {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '110',
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 105,
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 120)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 110)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert test(self.hass)

    def test_exor_many_conditions(self):
        """Test the 'exor' condition with more than two conditions."""
        test = condition.from_config({
            'condition': 'exor',
            'conditions': [
                {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '110',
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 120,
                }, {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '130',
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 110)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 130)
        assert test(self.hass)

    def test_exor_condition_with_template(self):
        """Test the 'exor' condition."""
        test = condition.from_config({
            'condition': 'exor',
            'conditions': [
                {
                    'condition': 'template',
                    'value_template':
                    '{{ states.sensor.temperature.state == "110" }}',
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 105,
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 120)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 110)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert test(self.hass)

    def test_nand_condition(self):
        """Test the 'nand' condition."""
        test = condition.from_config({
            'condition': 'nand',
            'conditions': [
                {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '100',
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 105,
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 120)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 101)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert not test(self.hass)

    def test_nand_many_conditions(self):
        """Test the 'nand' condition with more than two conditions."""
        test = condition.from_config({
            'condition': 'nand',
            'conditions': [
                {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 110,
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 120,
                }, {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '100',
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 110)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 130)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert not test(self.hass)

    def test_nand_condition_with_template(self):
        """Test the 'nand' condition."""
        test = condition.from_config({
            'condition': 'nand',
            'conditions': [
                {
                    'condition': 'template',
                    'value_template':
                    '{{ states.sensor.temperature.state == "100" }}',
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 105,
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 120)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 101)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert not test(self.hass)

    def test_nor_condition(self):
        """Test the 'nor' condition."""
        test = condition.from_config({
            'condition': 'nor',
            'conditions': [
                {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '100',
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 105,
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 120)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 101)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert not test(self.hass)

    def test_nor_many_conditions(self):
        """Test the 'nor' condition with more than two conditions."""
        test = condition.from_config({
            'condition': 'nor',
            'conditions': [
                {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 110,
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 120,
                }, {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '100',
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 110)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 130)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 105)
        assert not test(self.hass)

    def test_nor_condition_with_template(self):
        """Test the 'nor' condition."""
        test = condition.from_config({
            'condition': 'nor',
            'conditions': [
                {
                    'condition': 'template',
                    'value_template':
                    '{{ states.sensor.temperature.state == "100" }}',
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 105,
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 120)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 101)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert not test(self.hass)

    def test_xnor_condition(self):
        """Test the 'xnor' condition."""
        test = condition.from_config({
            'condition': 'xnor',
            'conditions': [
                {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '100',
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 105,
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 120)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 101)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert test(self.hass)

    def test_xnor_many_conditions(self):
        """Test the 'xnor' condition with more than two conditions."""
        test = condition.from_config({
            'condition': 'xnor',
            'conditions': [
                {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 110,
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 120,
                }, {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '100',
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 109)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 119)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 130)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert test(self.hass)

    def test_xnor_condition_with_template(self):
        """Test the 'xnor' condition."""
        test = condition.from_config({
            'condition': 'xnor',
            'conditions': [
                {
                    'condition': 'template',
                    'value_template':
                    '{{ states.sensor.temperature.state == "100" }}',
                }, {
                    'condition': 'numeric_state',
                    'entity_id': 'sensor.temperature',
                    'below': 105,
                }
            ]
        })

        self.hass.states.set('sensor.temperature', 120)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 101)
        assert not test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert test(self.hass)

    def test_not_condition(self):
        """Test the 'not' condition."""
        test = condition.from_config({
            'condition': 'not',
            'invert_condition': {
                    'condition': 'state',
                    'entity_id': 'sensor.temperature',
                    'state': '100',
                }
        })

        self.hass.states.set('sensor.temperature', 120)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert not test(self.hass)

    def test_not_condition_with_template(self):
        """Test the 'not' condition."""
        test = condition.from_config({
            'condition': 'not',
            'invert_condition': {
                    'condition': 'template',
                    'value_template':
                    '{{ states.sensor.temperature.state == "100" }}',
                }
        })

        self.hass.states.set('sensor.temperature', 120)
        assert test(self.hass)

        self.hass.states.set('sensor.temperature', 100)
        assert not test(self.hass)

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

    def test_if_numeric_state_not_raise_on_unavailable(self):
        """Test numeric_state doesn't raise on unavailable/unknown state."""
        test = condition.from_config({
            'condition': 'numeric_state',
            'entity_id': 'sensor.temperature',
            'below': 42
        })

        with patch('homeassistant.helpers.condition._LOGGER.warning') \
                as logwarn:
            self.hass.states.set('sensor.temperature', 'unavailable')
            assert not test(self.hass)
            assert len(logwarn.mock_calls) == 0

            self.hass.states.set('sensor.temperature', 'unknown')
            assert not test(self.hass)
            assert len(logwarn.mock_calls) == 0
