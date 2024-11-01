"""Test the condition helper."""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import pytest
import voluptuous as vol

from homeassistant.components import automation
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConditionError, HomeAssistantError
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    entity_registry as er,
    trace,
)
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.typing import WebSocketGenerator


def assert_element(trace_element, expected_element, path):
    """Assert a trace element is as expected.

    Note: Unused variable 'path' is passed to get helpful errors from pytest.
    """
    expected_result = expected_element.get("result", {})
    # Check that every item in expected_element is present and equal in trace_element
    # The redundant set operation gives helpful errors from pytest
    assert not set(expected_result) - set(trace_element._result or {})
    for result_key, result in expected_result.items():
        assert trace_element._result[result_key] == result

    # Check for unexpected items in trace_element
    assert not set(trace_element._result or {}) - set(expected_result)

    if "error_type" in expected_element:
        assert isinstance(trace_element._error, expected_element["error_type"])
    else:
        assert trace_element._error is None


@pytest.fixture(autouse=True)
def prepare_condition_trace() -> None:
    """Clear previous trace."""
    trace.trace_clear()


def assert_condition_trace(expected):
    """Assert a trace condition sequence is as expected."""
    condition_trace = trace.trace_get(clear=False)
    trace.trace_clear()
    expected_trace_keys = list(expected.keys())
    assert list(condition_trace.keys()) == expected_trace_keys
    for trace_key_index, key in enumerate(expected_trace_keys):
        assert len(condition_trace[key]) == len(expected[key])
        for index, element in enumerate(expected[key]):
            path = f"[{trace_key_index}][{index}]"
            assert_element(condition_trace[key][index], element, path)


async def test_invalid_condition(hass: HomeAssistant) -> None:
    """Test if invalid condition raises."""
    with pytest.raises(HomeAssistantError):
        await condition.async_from_config(
            hass,
            {
                "condition": "invalid",
                "conditions": [
                    {
                        "condition": "state",
                        "entity_id": "sensor.temperature",
                        "state": "100",
                    },
                ],
            },
        )


async def test_and_condition(hass: HomeAssistant) -> None:
    """Test the 'and' condition."""
    config = {
        "alias": "And Condition",
        "condition": "and",
        "conditions": [
            {
                "condition": "state",
                "entity_id": "sensor.temperature",
                "state": "100",
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 110,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    with pytest.raises(ConditionError):
        test(hass)
    assert_condition_trace(
        {
            "": [{"error_type": ConditionError}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"error_type": ConditionError}],
            "conditions/1/entity_id/0": [{"error_type": ConditionError}],
        }
    )

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [{"result": {"result": False}}],
            "conditions/0/entity_id/0": [
                {"result": {"result": False, "state": "120", "wanted_state": "100"}}
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 105)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [{"result": {"result": False}}],
            "conditions/0/entity_id/0": [
                {"result": {"result": False, "state": "105", "wanted_state": "100"}}
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": True}}],
            "conditions/0/entity_id/0": [
                {"result": {"result": True, "state": "100", "wanted_state": "100"}}
            ],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 100.0}}],
        }
    )


async def test_and_condition_raises(hass: HomeAssistant) -> None:
    """Test the 'and' condition."""
    config = {
        "alias": "And Condition",
        "condition": "and",
        "conditions": [
            {
                "condition": "state",
                "entity_id": "sensor.temperature",
                "state": "100",
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature2",
                "above": 110,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    # All subconditions raise, the AND-condition should raise
    with pytest.raises(ConditionError):
        test(hass)
    assert_condition_trace(
        {
            "": [{"error_type": ConditionError}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"error_type": ConditionError}],
            "conditions/1/entity_id/0": [{"error_type": ConditionError}],
        }
    )

    # The first subconditions raises, the second returns True, the AND-condition
    # should raise
    hass.states.async_set("sensor.temperature2", 120)
    with pytest.raises(ConditionError):
        test(hass)
    assert_condition_trace(
        {
            "": [{"error_type": ConditionError}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 120.0}}],
        }
    )

    # The first subconditions raises, the second returns False, the AND-condition
    # should return False
    hass.states.async_set("sensor.temperature2", 90)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"result": {"result": False}}],
            "conditions/1/entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "state": 90.0,
                        "wanted_state_above": 110.0,
                    }
                }
            ],
        }
    )


async def test_and_condition_with_template(hass: HomeAssistant) -> None:
    """Test the 'and' condition."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "alias": "Template Condition",
                "condition": "template",
                "value_template": '{{ states.sensor.temperature.state == "100" }}',
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 110,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [
                {"result": {"entities": ["sensor.temperature"], "result": False}}
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 105)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)


async def test_and_condition_shorthand(hass: HomeAssistant) -> None:
    """Test the 'and' condition shorthand."""
    config = {
        "alias": "And Condition Shorthand",
        "and": [
            {
                "alias": "Template Condition",
                "condition": "template",
                "value_template": '{{ states.sensor.temperature.state == "100" }}',
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 110,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    assert config["alias"] == "And Condition Shorthand"
    assert "and" not in config

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [
                {"result": {"entities": ["sensor.temperature"], "result": False}}
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 105)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)


async def test_and_condition_list_shorthand(hass: HomeAssistant) -> None:
    """Test the 'and' condition list shorthand."""
    config = {
        "alias": "And Condition List Shorthand",
        "condition": [
            {
                "alias": "Template Condition",
                "condition": "template",
                "value_template": '{{ states.sensor.temperature.state == "100" }}',
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 110,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    assert config["alias"] == "And Condition List Shorthand"
    assert "and" not in config

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [
                {"result": {"entities": ["sensor.temperature"], "result": False}}
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 105)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)


async def test_malformed_and_condition_list_shorthand(hass: HomeAssistant) -> None:
    """Test the 'and' condition list shorthand syntax check."""
    config = {
        "alias": "Bad shorthand syntax",
        "condition": ["bad", "syntax"],
    }

    with pytest.raises(vol.MultipleInvalid):
        cv.CONDITION_SCHEMA(config)


async def test_or_condition(hass: HomeAssistant) -> None:
    """Test the 'or' condition."""
    config = {
        "alias": "Or Condition",
        "condition": "or",
        "conditions": [
            {
                "condition": "state",
                "entity_id": "sensor.temperature",
                "state": "100",
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 110,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    with pytest.raises(ConditionError):
        test(hass)
    assert_condition_trace(
        {
            "": [{"error_type": ConditionError}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"error_type": ConditionError}],
            "conditions/1/entity_id/0": [{"error_type": ConditionError}],
        }
    )

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [{"result": {"result": False}}],
            "conditions/0/entity_id/0": [
                {"result": {"result": False, "state": "120", "wanted_state": "100"}}
            ],
            "conditions/1": [{"result": {"result": False}}],
            "conditions/1/entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "state": 120.0,
                        "wanted_state_below": 110.0,
                    }
                }
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 105)
    assert test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": False}}],
            "conditions/0/entity_id/0": [
                {"result": {"result": False, "state": "105", "wanted_state": "100"}}
            ],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 105.0}}],
        }
    )

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": True}}],
            "conditions/0/entity_id/0": [
                {"result": {"result": True, "state": "100", "wanted_state": "100"}}
            ],
        }
    )


async def test_or_condition_raises(hass: HomeAssistant) -> None:
    """Test the 'or' condition."""
    config = {
        "alias": "Or Condition",
        "condition": "or",
        "conditions": [
            {
                "condition": "state",
                "entity_id": "sensor.temperature",
                "state": "100",
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature2",
                "above": 110,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    # All subconditions raise, the OR-condition should raise
    with pytest.raises(ConditionError):
        test(hass)
    assert_condition_trace(
        {
            "": [{"error_type": ConditionError}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"error_type": ConditionError}],
            "conditions/1/entity_id/0": [{"error_type": ConditionError}],
        }
    )

    # The first subconditions raises, the second returns False, the OR-condition
    # should raise
    hass.states.async_set("sensor.temperature2", 100)
    with pytest.raises(ConditionError):
        test(hass)
    assert_condition_trace(
        {
            "": [{"error_type": ConditionError}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"result": {"result": False}}],
            "conditions/1/entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "state": 100.0,
                        "wanted_state_above": 110.0,
                    }
                }
            ],
        }
    )

    # The first subconditions raises, the second returns True, the OR-condition
    # should return True
    hass.states.async_set("sensor.temperature2", 120)
    assert test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 120.0}}],
        }
    )


async def test_or_condition_with_template(hass: HomeAssistant) -> None:
    """Test the 'or' condition."""
    config = {
        "condition": "or",
        "conditions": [
            {'{{ states.sensor.temperature.state == "100" }}'},
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 110,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 105)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)


async def test_or_condition_shorthand(hass: HomeAssistant) -> None:
    """Test the 'or' condition shorthand."""
    config = {
        "alias": "Or Condition Shorthand",
        "or": [
            {'{{ states.sensor.temperature.state == "100" }}'},
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 110,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    assert config["alias"] == "Or Condition Shorthand"
    assert "or" not in config

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 105)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)


async def test_not_condition(hass: HomeAssistant) -> None:
    """Test the 'not' condition."""
    config = {
        "alias": "Not Condition",
        "condition": "not",
        "conditions": [
            {
                "condition": "state",
                "entity_id": "sensor.temperature",
                "state": "100",
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 50,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    with pytest.raises(ConditionError):
        test(hass)
    assert_condition_trace(
        {
            "": [{"error_type": ConditionError}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"error_type": ConditionError}],
            "conditions/1/entity_id/0": [{"error_type": ConditionError}],
        }
    )

    hass.states.async_set("sensor.temperature", 101)
    assert test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": False}}],
            "conditions/0/entity_id/0": [
                {"result": {"result": False, "state": "101", "wanted_state": "100"}}
            ],
            "conditions/1": [{"result": {"result": False}}],
            "conditions/1/entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "state": 101.0,
                        "wanted_state_below": 50.0,
                    }
                }
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 50)
    assert test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": False}}],
            "conditions/0/entity_id/0": [
                {"result": {"result": False, "state": "50", "wanted_state": "100"}}
            ],
            "conditions/1": [{"result": {"result": False}}],
            "conditions/1/entity_id/0": [
                {"result": {"result": False, "state": 50.0, "wanted_state_below": 50.0}}
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 49)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [{"result": {"result": False}}],
            "conditions/0/entity_id/0": [
                {"result": {"result": False, "state": "49", "wanted_state": "100"}}
            ],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 49.0}}],
        }
    )

    hass.states.async_set("sensor.temperature", 100)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [{"result": {"result": True}}],
            "conditions/0/entity_id/0": [
                {"result": {"result": True, "state": "100", "wanted_state": "100"}}
            ],
        }
    )


async def test_not_condition_raises(hass: HomeAssistant) -> None:
    """Test the 'and' condition."""
    config = {
        "alias": "Not Condition",
        "condition": "not",
        "conditions": [
            {
                "condition": "state",
                "entity_id": "sensor.temperature",
                "state": "100",
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature2",
                "below": 50,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    # All subconditions raise, the NOT-condition should raise
    with pytest.raises(ConditionError):
        test(hass)
    assert_condition_trace(
        {
            "": [{"error_type": ConditionError}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"error_type": ConditionError}],
            "conditions/1/entity_id/0": [{"error_type": ConditionError}],
        }
    )

    # The first subconditions raises, the second returns False, the NOT-condition
    # should raise
    hass.states.async_set("sensor.temperature2", 90)
    with pytest.raises(ConditionError):
        test(hass)
    assert_condition_trace(
        {
            "": [{"error_type": ConditionError}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"result": {"result": False}}],
            "conditions/1/entity_id/0": [
                {"result": {"result": False, "state": 90.0, "wanted_state_below": 50.0}}
            ],
        }
    )

    # The first subconditions raises, the second returns True, the NOT-condition
    # should return False
    hass.states.async_set("sensor.temperature2", 40)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [{"error_type": ConditionError}],
            "conditions/0/entity_id/0": [{"error_type": ConditionError}],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 40.0}}],
        }
    )


async def test_not_condition_with_template(hass: HomeAssistant) -> None:
    """Test the 'or' condition."""
    config = {
        "condition": "not",
        "conditions": [
            {
                "condition": "template",
                "value_template": '{{ states.sensor.temperature.state == "100" }}',
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 50,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 101)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 50)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 49)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert not test(hass)


async def test_not_condition_shorthand(hass: HomeAssistant) -> None:
    """Test the 'or' condition shorthand."""
    config = {
        "alias": "Not Condition Shorthand",
        "not": [
            {
                "condition": "template",
                "value_template": '{{ states.sensor.temperature.state == "100" }}',
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 50,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    assert config["alias"] == "Not Condition Shorthand"
    assert "not" not in config

    hass.states.async_set("sensor.temperature", 101)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 50)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 49)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert not test(hass)


async def test_time_window(hass: HomeAssistant) -> None:
    """Test time condition windows."""
    sixam = "06:00:00"
    sixpm = "18:00:00"

    config1 = {
        "alias": "Time Cond",
        "condition": "time",
        "after": sixam,
        "before": sixpm,
    }
    config1 = cv.CONDITION_SCHEMA(config1)
    config1 = await condition.async_validate_condition_config(hass, config1)
    config2 = {
        "alias": "Time Cond",
        "condition": "time",
        "after": sixpm,
        "before": sixam,
    }
    config2 = cv.CONDITION_SCHEMA(config2)
    config2 = await condition.async_validate_condition_config(hass, config2)
    test1 = await condition.async_from_config(hass, config1)
    test2 = await condition.async_from_config(hass, config2)

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=3),
    ):
        assert not test1(hass)
        assert test2(hass)

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=9),
    ):
        assert test1(hass)
        assert not test2(hass)

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=15),
    ):
        assert test1(hass)
        assert not test2(hass)

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=21),
    ):
        assert not test1(hass)
        assert test2(hass)


async def test_time_using_input_datetime(hass: HomeAssistant) -> None:
    """Test time conditions using input_datetime entities."""
    await async_setup_component(
        hass,
        "input_datetime",
        {
            "input_datetime": {
                "am": {"has_date": True, "has_time": True},
                "pm": {"has_date": True, "has_time": True},
            }
        },
    )

    await hass.services.async_call(
        "input_datetime",
        "set_datetime",
        {
            "entity_id": "input_datetime.am",
            "datetime": str(
                dt_util.now()
                .replace(hour=6, minute=0, second=0, microsecond=0)
                .replace(tzinfo=None)
            ),
        },
        blocking=True,
    )

    await hass.services.async_call(
        "input_datetime",
        "set_datetime",
        {
            "entity_id": "input_datetime.pm",
            "datetime": str(
                dt_util.now()
                .replace(hour=18, minute=0, second=0, microsecond=0)
                .replace(tzinfo=None)
            ),
        },
        blocking=True,
    )

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=3),
    ):
        assert not condition.time(
            hass, after="input_datetime.am", before="input_datetime.pm"
        )
        assert condition.time(
            hass, after="input_datetime.pm", before="input_datetime.am"
        )

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=9),
    ):
        assert condition.time(
            hass, after="input_datetime.am", before="input_datetime.pm"
        )
        assert not condition.time(
            hass, after="input_datetime.pm", before="input_datetime.am"
        )

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=15),
    ):
        assert condition.time(
            hass, after="input_datetime.am", before="input_datetime.pm"
        )
        assert not condition.time(
            hass, after="input_datetime.pm", before="input_datetime.am"
        )

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=21),
    ):
        assert not condition.time(
            hass, after="input_datetime.am", before="input_datetime.pm"
        )
        assert condition.time(
            hass, after="input_datetime.pm", before="input_datetime.am"
        )

    # Trigger on PM time
    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=18, minute=0, second=0),
    ):
        assert condition.time(
            hass, after="input_datetime.pm", before="input_datetime.am"
        )
        assert not condition.time(
            hass, after="input_datetime.am", before="input_datetime.pm"
        )
        assert condition.time(hass, after="input_datetime.pm")
        assert not condition.time(hass, before="input_datetime.pm")

    # Trigger on AM time
    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=6, minute=0, second=0),
    ):
        assert not condition.time(
            hass, after="input_datetime.pm", before="input_datetime.am"
        )
        assert condition.time(
            hass, after="input_datetime.am", before="input_datetime.pm"
        )
        assert condition.time(hass, after="input_datetime.am")
        assert not condition.time(hass, before="input_datetime.am")

    with pytest.raises(ConditionError):
        condition.time(hass, after="input_datetime.not_existing")

    with pytest.raises(ConditionError):
        condition.time(hass, before="input_datetime.not_existing")


async def test_time_using_sensor(hass: HomeAssistant) -> None:
    """Test time conditions using sensor entities."""
    hass.states.async_set(
        "sensor.am",
        "2021-06-03 13:00:00.000000+00:00",  # 6 am local time
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
    )
    hass.states.async_set(
        "sensor.pm",
        "2020-06-01 01:00:00.000000+00:00",  # 6 pm local time
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
    )
    hass.states.async_set(
        "sensor.no_device_class",
        "2020-06-01 01:00:00.000000+00:00",
    )
    hass.states.async_set(
        "sensor.invalid_timestamp",
        "This is not a timestamp",
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
    )

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=3),
    ):
        assert not condition.time(hass, after="sensor.am", before="sensor.pm")
        assert condition.time(hass, after="sensor.pm", before="sensor.am")

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=9),
    ):
        assert condition.time(hass, after="sensor.am", before="sensor.pm")
        assert not condition.time(hass, after="sensor.pm", before="sensor.am")

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=15),
    ):
        assert condition.time(hass, after="sensor.am", before="sensor.pm")
        assert not condition.time(hass, after="sensor.pm", before="sensor.am")

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=21),
    ):
        assert not condition.time(hass, after="sensor.am", before="sensor.pm")
        assert condition.time(hass, after="sensor.pm", before="sensor.am")

    # Trigger on PM time
    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=18, minute=0, second=0),
    ):
        assert condition.time(hass, after="sensor.pm", before="sensor.am")
        assert not condition.time(hass, after="sensor.am", before="sensor.pm")
        assert condition.time(hass, after="sensor.pm")
        assert not condition.time(hass, before="sensor.pm")

        # Even though valid, the device class is missing
        assert not condition.time(hass, after="sensor.no_device_class")
        assert not condition.time(hass, before="sensor.no_device_class")

    # Trigger on AM time
    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=6, minute=0, second=0),
    ):
        assert not condition.time(hass, after="sensor.pm", before="sensor.am")
        assert condition.time(hass, after="sensor.am", before="sensor.pm")
        assert condition.time(hass, after="sensor.am")
        assert not condition.time(hass, before="sensor.am")

    assert not condition.time(hass, after="sensor.invalid_timestamp")
    assert not condition.time(hass, before="sensor.invalid_timestamp")

    with pytest.raises(ConditionError):
        condition.time(hass, after="sensor.not_existing")

    with pytest.raises(ConditionError):
        condition.time(hass, before="sensor.not_existing")


async def test_state_raises(hass: HomeAssistant) -> None:
    """Test that state raises ConditionError on errors."""
    # No entity
    with pytest.raises(ConditionError, match="no entity"):
        condition.state(hass, entity=None, req_state="missing")

    # Unknown entities
    config = {
        "condition": "state",
        "entity_id": ["sensor.door_unknown", "sensor.window_unknown"],
        "state": "open",
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    with pytest.raises(ConditionError, match="unknown entity.*door"):
        test(hass)
    with pytest.raises(ConditionError, match="unknown entity.*window"):
        test(hass)

    # Unknown state entity

    config = {
        "condition": "state",
        "entity_id": "sensor.door",
        "state": "input_text.missing",
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.door", "open")
    with pytest.raises(ConditionError, match="input_text.missing"):
        test(hass)


async def test_state_for(hass: HomeAssistant) -> None:
    """Test state with duration."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "state",
                "entity_id": ["sensor.temperature"],
                "state": "100",
                "for": {"seconds": 5},
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 100)
    assert not test(hass)

    now = dt_util.utcnow() + timedelta(seconds=5)
    with freeze_time(now):
        assert test(hass)


async def test_state_for_template(hass: HomeAssistant) -> None:
    """Test state with templated duration."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "state",
                "entity_id": ["sensor.temperature"],
                "state": "100",
                "for": {"seconds": "{{ states('input_number.test')|int }}"},
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 100)
    hass.states.async_set("input_number.test", 5)
    assert not test(hass)

    now = dt_util.utcnow() + timedelta(seconds=5)
    with freeze_time(now):
        assert test(hass)


@pytest.mark.parametrize("for_template", [{"{{invalid}}": 5}, {"hours": "{{ 1/0 }}"}])
async def test_state_for_invalid_template(
    hass: HomeAssistant, for_template: dict[str, Any]
) -> None:
    """Test state with invalid templated duration."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "state",
                "entity_id": ["sensor.temperature"],
                "state": "100",
                "for": for_template,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 100)
    hass.states.async_set("input_number.test", 5)
    with pytest.raises(ConditionError):
        assert not test(hass)


async def test_state_unknown_attribute(hass: HomeAssistant) -> None:
    """Test that state returns False on unknown attribute."""
    # Unknown attribute
    config = {
        "condition": "state",
        "entity_id": "sensor.door",
        "attribute": "model",
        "state": "acme",
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.door", "open")
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "message": (
                            "attribute 'model' of entity sensor.door does not exist"
                        ),
                    }
                }
            ],
        }
    )


async def test_state_multiple_entities(hass: HomeAssistant) -> None:
    """Test with multiple entities in condition."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "state",
                "entity_id": ["sensor.temperature_1", "sensor.temperature_2"],
                "state": "100",
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature_1", 100)
    hass.states.async_set("sensor.temperature_2", 100)
    assert test(hass)

    hass.states.async_set("sensor.temperature_1", 101)
    hass.states.async_set("sensor.temperature_2", 100)
    assert not test(hass)

    hass.states.async_set("sensor.temperature_1", 100)
    hass.states.async_set("sensor.temperature_2", 101)
    assert not test(hass)


async def test_state_multiple_entities_match_any(hass: HomeAssistant) -> None:
    """Test with multiple entities in condition with match any."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "state",
                "entity_id": ["sensor.temperature_1", "sensor.temperature_2"],
                "match": "any",
                "state": "100",
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature_1", 100)
    hass.states.async_set("sensor.temperature_2", 100)
    assert test(hass)

    hass.states.async_set("sensor.temperature_1", 101)
    hass.states.async_set("sensor.temperature_2", 100)
    assert test(hass)

    hass.states.async_set("sensor.temperature_1", 100)
    hass.states.async_set("sensor.temperature_2", 101)
    assert test(hass)

    hass.states.async_set("sensor.temperature_1", 101)
    hass.states.async_set("sensor.temperature_2", 101)
    assert not test(hass)


async def test_multiple_states(hass: HomeAssistant) -> None:
    """Test with multiple states in condition."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "alias": "State Condition",
                "condition": "state",
                "entity_id": "sensor.temperature",
                "state": ["100", "200"],
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 200)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 42)
    assert not test(hass)


async def test_state_attribute(hass: HomeAssistant) -> None:
    """Test with state attribute in condition."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "state",
                "entity_id": "sensor.temperature",
                "attribute": "attribute1",
                "state": 200,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 100, {"unknown_attr": 200})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 200})
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": "200"})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 201})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": None})
    assert not test(hass)


async def test_state_attribute_boolean(hass: HomeAssistant) -> None:
    """Test with boolean state attribute in condition."""
    config = {
        "condition": "state",
        "entity_id": "sensor.temperature",
        "attribute": "happening",
        "state": False,
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 100, {"happening": 200})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"happening": True})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"no_happening": 201})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"happening": False})
    assert test(hass)


async def test_state_entity_registry_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test with entity specified by entity registry id."""
    entry = entity_registry.async_get_or_create(
        "switch", "hue", "1234", suggested_object_id="test"
    )
    assert entry.entity_id == "switch.test"
    config = {
        "condition": "state",
        "entity_id": entry.id,
        "state": "on",
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("switch.test", "on")
    assert test(hass)

    hass.states.async_set("switch.test", "off")
    assert not test(hass)


async def test_state_using_input_entities(hass: HomeAssistant) -> None:
    """Test state conditions using input_* entities."""
    await async_setup_component(
        hass,
        "input_text",
        {
            "input_text": {
                "hello": {"initial": "goodbye"},
            }
        },
    )

    await async_setup_component(
        hass,
        "input_select",
        {
            "input_select": {
                "hello": {"options": ["cya", "goodbye", "welcome"], "initial": "cya"},
            }
        },
    )

    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "state",
                "entity_id": "sensor.salut",
                "state": [
                    "input_text.hello",
                    "input_select.hello",
                    "salut",
                ],
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.salut", "goodbye")
    assert test(hass)

    hass.states.async_set("sensor.salut", "salut")
    assert test(hass)

    hass.states.async_set("sensor.salut", "hello")
    assert not test(hass)

    await hass.services.async_call(
        "input_text",
        "set_value",
        {
            "entity_id": "input_text.hello",
            "value": "hi",
        },
        blocking=True,
    )
    assert not test(hass)

    hass.states.async_set("sensor.salut", "hi")
    assert test(hass)

    hass.states.async_set("sensor.salut", "cya")
    assert test(hass)

    await hass.services.async_call(
        "input_select",
        "select_option",
        {
            "entity_id": "input_select.hello",
            "option": "welcome",
        },
        blocking=True,
    )
    assert not test(hass)

    hass.states.async_set("sensor.salut", "welcome")
    assert test(hass)


async def test_numeric_state_known_non_matching(hass: HomeAssistant) -> None:
    """Test that numeric_state doesn't match on known non-matching states."""
    hass.states.async_set("sensor.temperature", "unavailable")
    config = {
        "condition": "numeric_state",
        "entity_id": "sensor.temperature",
        "above": 0,
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    # Unavailable state
    assert not test(hass)

    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "message": (
                            "value 'unavailable' is non-numeric and treated as False"
                        ),
                    }
                }
            ],
        }
    )

    # Unknown state
    hass.states.async_set("sensor.temperature", "unknown")
    assert not test(hass)

    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "message": (
                            "value 'unknown' is non-numeric and treated as False"
                        ),
                    }
                }
            ],
        }
    )


async def test_numeric_state_raises(hass: HomeAssistant) -> None:
    """Test that numeric_state raises ConditionError on errors."""
    # Unknown entities
    config = {
        "condition": "numeric_state",
        "entity_id": ["sensor.temperature_unknown", "sensor.humidity_unknown"],
        "above": 0,
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    with pytest.raises(ConditionError, match="unknown entity.*temperature"):
        test(hass)
    with pytest.raises(ConditionError, match="unknown entity.*humidity"):
        test(hass)

    # Template error
    config = {
        "condition": "numeric_state",
        "entity_id": "sensor.temperature",
        "value_template": "{{ 1 / 0 }}",
        "above": 0,
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 50)
    with pytest.raises(ConditionError, match="ZeroDivisionError"):
        test(hass)

    # Bad number
    config = {
        "condition": "numeric_state",
        "entity_id": "sensor.temperature",
        "above": 0,
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", "fifty")
    with pytest.raises(ConditionError, match="cannot be processed as a number"):
        test(hass)

    # Below entity missing
    config = {
        "condition": "numeric_state",
        "entity_id": "sensor.temperature",
        "below": "input_number.missing",
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 50)
    with pytest.raises(ConditionError, match="'below' entity"):
        test(hass)

    # Below entity not a number
    hass.states.async_set("input_number.missing", "number")
    with pytest.raises(
        ConditionError,
        match="'below'.*input_number.missing.*cannot be processed as a number",
    ):
        test(hass)

    # Above entity missing
    config = {
        "condition": "numeric_state",
        "entity_id": "sensor.temperature",
        "above": "input_number.missing",
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 50)
    with pytest.raises(ConditionError, match="'above' entity"):
        test(hass)

    # Above entity not a number
    hass.states.async_set("input_number.missing", "number")
    with pytest.raises(
        ConditionError,
        match="'above'.*input_number.missing.*cannot be processed as a number",
    ):
        test(hass)


async def test_numeric_state_unknown_attribute(hass: HomeAssistant) -> None:
    """Test that numeric_state returns False on unknown attribute."""
    # Unknown attribute
    config = {
        "condition": "numeric_state",
        "entity_id": "sensor.temperature",
        "attribute": "temperature",
        "above": 0,
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 50)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "message": (
                            "attribute 'temperature' of entity sensor.temperature does"
                            " not exist"
                        ),
                    }
                }
            ],
        }
    )


async def test_numeric_state_multiple_entities(hass: HomeAssistant) -> None:
    """Test with multiple entities in condition."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "alias": "Numeric State Condition",
                "condition": "numeric_state",
                "entity_id": ["sensor.temperature_1", "sensor.temperature_2"],
                "below": 50,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature_1", 49)
    hass.states.async_set("sensor.temperature_2", 49)
    assert test(hass)

    hass.states.async_set("sensor.temperature_1", 50)
    hass.states.async_set("sensor.temperature_2", 49)
    assert not test(hass)

    hass.states.async_set("sensor.temperature_1", 49)
    hass.states.async_set("sensor.temperature_2", 50)
    assert not test(hass)


async def test_numeric_state_attribute(hass: HomeAssistant) -> None:
    """Test with numeric state attribute in condition."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "attribute": "attribute1",
                "below": 50,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 100, {"unknown_attr": 10})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 49})
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": "49"})
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 51})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": None})
    assert not test(hass)


async def test_numeric_state_entity_registry_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test with entity specified by entity registry id."""
    entry = entity_registry.async_get_or_create(
        "sensor", "hue", "1234", suggested_object_id="test"
    )
    assert entry.entity_id == "sensor.test"
    config = {
        "condition": "numeric_state",
        "entity_id": entry.id,
        "above": 100,
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.test", "110")
    assert test(hass)

    hass.states.async_set("sensor.test", "90")
    assert not test(hass)


async def test_numeric_state_using_input_number(hass: HomeAssistant) -> None:
    """Test numeric_state conditions using input_number entities."""
    hass.states.async_set("number.low", 10)
    await async_setup_component(
        hass,
        "input_number",
        {
            "input_number": {
                "high": {"min": 0, "max": 255, "initial": 100},
            }
        },
    )

    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": "input_number.high",
                "above": "number.low",
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 42)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 10)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert not test(hass)

    hass.states.async_set("input_number.high", "unknown")
    assert not test(hass)

    hass.states.async_set("input_number.high", "unavailable")
    assert not test(hass)

    await hass.services.async_call(
        "input_number",
        "set_value",
        {
            "entity_id": "input_number.high",
            "value": 101,
        },
        blocking=True,
    )
    assert test(hass)

    hass.states.async_set("number.low", "unknown")
    assert not test(hass)

    hass.states.async_set("number.low", "unavailable")
    assert not test(hass)

    with pytest.raises(ConditionError):
        condition.async_numeric_state(
            hass, entity="sensor.temperature", below="input_number.not_exist"
        )
    with pytest.raises(ConditionError):
        condition.async_numeric_state(
            hass, entity="sensor.temperature", above="input_number.not_exist"
        )


async def test_zone_raises(hass: HomeAssistant) -> None:
    """Test that zone raises ConditionError on errors."""
    config = {
        "condition": "zone",
        "entity_id": "device_tracker.cat",
        "zone": "zone.home",
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    with pytest.raises(ConditionError, match="no zone"):
        condition.zone(hass, zone_ent=None, entity="sensor.any")

    with pytest.raises(ConditionError, match="unknown zone"):
        test(hass)

    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )

    with pytest.raises(ConditionError, match="no entity"):
        condition.zone(hass, zone_ent="zone.home", entity=None)

    with pytest.raises(ConditionError, match="unknown entity"):
        test(hass)

    hass.states.async_set(
        "device_tracker.cat",
        "home",
        {"friendly_name": "cat"},
    )

    with pytest.raises(ConditionError, match="latitude"):
        test(hass)

    hass.states.async_set(
        "device_tracker.cat",
        "home",
        {"friendly_name": "cat", "latitude": 2.1},
    )

    with pytest.raises(ConditionError, match="longitude"):
        test(hass)

    hass.states.async_set(
        "device_tracker.cat",
        "home",
        {"friendly_name": "cat", "latitude": 2.1, "longitude": 1.1},
    )

    # All okay, now test multiple failed conditions
    assert test(hass)

    config = {
        "condition": "zone",
        "entity_id": ["device_tracker.cat", "device_tracker.dog"],
        "zone": ["zone.home", "zone.work"],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    with pytest.raises(ConditionError, match="dog"):
        test(hass)

    with pytest.raises(ConditionError, match="work"):
        test(hass)

    hass.states.async_set(
        "zone.work",
        "zoning",
        {"name": "work", "latitude": 20, "longitude": 10, "radius": 25000},
    )

    hass.states.async_set(
        "device_tracker.dog",
        "work",
        {"friendly_name": "dog", "latitude": 20.1, "longitude": 10.1},
    )

    assert test(hass)


async def test_zone_multiple_entities(hass: HomeAssistant) -> None:
    """Test with multiple entities in condition."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "alias": "Zone Condition",
                "condition": "zone",
                "entity_id": ["device_tracker.person_1", "device_tracker.person_2"],
                "zone": "zone.home",
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )

    hass.states.async_set(
        "device_tracker.person_1",
        "home",
        {"friendly_name": "person_1", "latitude": 2.1, "longitude": 1.1},
    )
    hass.states.async_set(
        "device_tracker.person_2",
        "home",
        {"friendly_name": "person_2", "latitude": 2.1, "longitude": 1.1},
    )
    assert test(hass)

    hass.states.async_set(
        "device_tracker.person_1",
        "home",
        {"friendly_name": "person_1", "latitude": 20.1, "longitude": 10.1},
    )
    hass.states.async_set(
        "device_tracker.person_2",
        "home",
        {"friendly_name": "person_2", "latitude": 2.1, "longitude": 1.1},
    )
    assert not test(hass)

    hass.states.async_set(
        "device_tracker.person_1",
        "home",
        {"friendly_name": "person_1", "latitude": 2.1, "longitude": 1.1},
    )
    hass.states.async_set(
        "device_tracker.person_2",
        "home",
        {"friendly_name": "person_2", "latitude": 20.1, "longitude": 10.1},
    )
    assert not test(hass)


async def test_multiple_zones(hass: HomeAssistant) -> None:
    """Test with multiple entities in condition."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "zone",
                "entity_id": "device_tracker.person",
                "zone": ["zone.home", "zone.work"],
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )
    hass.states.async_set(
        "zone.work",
        "zoning",
        {"name": "work", "latitude": 20.1, "longitude": 10.1, "radius": 10},
    )

    hass.states.async_set(
        "device_tracker.person",
        "home",
        {"friendly_name": "person", "latitude": 2.1, "longitude": 1.1},
    )
    assert test(hass)

    hass.states.async_set(
        "device_tracker.person",
        "home",
        {"friendly_name": "person", "latitude": 20.1, "longitude": 10.1},
    )
    assert test(hass)

    hass.states.async_set(
        "device_tracker.person",
        "home",
        {"friendly_name": "person", "latitude": 50.1, "longitude": 20.1},
    )
    assert not test(hass)


async def test_extract_entities() -> None:
    """Test extracting entities."""
    assert condition.async_extract_entities(
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "state",
                    "entity_id": "sensor.temperature",
                    "state": "100",
                },
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.temperature_2",
                    "below": 110,
                },
                {
                    "condition": "not",
                    "conditions": [
                        {
                            "condition": "state",
                            "entity_id": "sensor.temperature_3",
                            "state": "100",
                        },
                        {
                            "condition": "numeric_state",
                            "entity_id": "sensor.temperature_4",
                            "below": 110,
                        },
                    ],
                },
                {
                    "condition": "or",
                    "conditions": [
                        {
                            "condition": "state",
                            "entity_id": "sensor.temperature_5",
                            "state": "100",
                        },
                        {
                            "condition": "numeric_state",
                            "entity_id": "sensor.temperature_6",
                            "below": 110,
                        },
                    ],
                },
                {
                    "condition": "state",
                    "entity_id": ["sensor.temperature_7", "sensor.temperature_8"],
                    "state": "100",
                },
                {
                    "condition": "numeric_state",
                    "entity_id": ["sensor.temperature_9", "sensor.temperature_10"],
                    "below": 110,
                },
                Template("{{ is_state('light.example', 'on') }}"),
            ],
        }
    ) == {
        "sensor.temperature",
        "sensor.temperature_2",
        "sensor.temperature_3",
        "sensor.temperature_4",
        "sensor.temperature_5",
        "sensor.temperature_6",
        "sensor.temperature_7",
        "sensor.temperature_8",
        "sensor.temperature_9",
        "sensor.temperature_10",
    }


async def test_extract_devices() -> None:
    """Test extracting devices."""
    assert condition.async_extract_devices(
        {
            "condition": "and",
            "conditions": [
                {"condition": "device", "device_id": "abcd", "domain": "light"},
                {"condition": "device", "device_id": "qwer", "domain": "switch"},
                {
                    "condition": "state",
                    "entity_id": "sensor.not_a_device",
                    "state": "100",
                },
                {
                    "condition": "not",
                    "conditions": [
                        {
                            "condition": "device",
                            "device_id": "abcd_not",
                            "domain": "light",
                        },
                        {
                            "condition": "device",
                            "device_id": "qwer_not",
                            "domain": "switch",
                        },
                    ],
                },
                {
                    "condition": "or",
                    "conditions": [
                        {
                            "condition": "device",
                            "device_id": "abcd_or",
                            "domain": "light",
                        },
                        {
                            "condition": "device",
                            "device_id": "qwer_or",
                            "domain": "switch",
                        },
                    ],
                },
                Template("{{ is_state('light.example', 'on') }}"),
            ],
        }
    ) == {"abcd", "qwer", "abcd_not", "qwer_not", "abcd_or", "qwer_or"}


async def test_condition_template_error(hass: HomeAssistant) -> None:
    """Test invalid template."""
    config = {"condition": "template", "value_template": "{{ undefined.state }}"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    with pytest.raises(ConditionError, match="template"):
        test(hass)


async def test_condition_template_invalid_results(hass: HomeAssistant) -> None:
    """Test template condition render false with invalid results."""
    config = {"condition": "template", "value_template": "{{ 'string' }}"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert not test(hass)

    config = {"condition": "template", "value_template": "{{ 10.1 }}"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert not test(hass)

    config = {"condition": "template", "value_template": "{{ 42 }}"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert not test(hass)

    config = {"condition": "template", "value_template": "{{ [1, 2, 3] }}"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert not test(hass)


def _find_run_id(traces, trace_type, item_id):
    """Find newest run_id for a script or automation."""
    for _trace in reversed(traces):
        if _trace["domain"] == trace_type and _trace["item_id"] == item_id:
            return _trace["run_id"]

    return None


async def assert_automation_condition_trace(hass_ws_client, automation_id, expected):
    """Test the result of automation condition."""
    msg_id = 1

    def next_id():
        nonlocal msg_id
        msg_id += 1
        return msg_id

    client = await hass_ws_client()

    # List traces
    await client.send_json(
        {"id": next_id(), "type": "trace/list", "domain": "automation"}
    )
    response = await client.receive_json()
    assert response["success"]
    run_id = _find_run_id(response["result"], "automation", automation_id)

    # Get trace
    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/get",
            "domain": "automation",
            "item_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    trace = response["result"]
    assert len(trace["trace"]["condition/0"]) == 1
    condition_trace = trace["trace"]["condition/0"][0]["result"]
    assert condition_trace == expected


async def test_if_action_before_sunrise_no_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunrise.

    Before sunrise is true from midnight until sunset, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "before": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise + 1s -> 'before sunrise' not true
    now = datetime(2015, 9, 16, 13, 33, 19, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = sunrise -> 'before sunrise' true
    now = datetime(2015, 9, 16, 13, 33, 18, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )


async def test_if_action_after_sunrise_no_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunrise.

    After sunrise is true from sunrise until midnight, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "after": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise - 1s -> 'after sunrise' not true
    now = datetime(2015, 9, 16, 13, 33, 17, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = sunrise + 1s -> 'after sunrise' true
    now = datetime(2015, 9, 16, 13, 33, 19, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight -> 'after sunrise' not true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight - 1s -> 'after sunrise' true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )


async def test_if_action_before_sunrise_with_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunrise with offset.

    Before sunrise is true from midnight until sunset, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "before": SUN_EVENT_SUNRISE,
                    "before_offset": "+1:00:00",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise + 1s + 1h -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 14, 33, 19, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunrise + 1h -> 'before sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 14, 33, 18, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC midnight -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 0, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC midnight - 1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 23, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight -> 'before sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 1, 53, 45, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset -1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 1, 53, 44, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )


async def test_if_action_before_sunset_with_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunset with offset.

    Before sunset is true from midnight until sunset, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "before": "sunset",
                    "before_offset": "+1:00:00",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = local midnight -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunset + 1s + 1h -> 'before sunset' with offset +1h not true
    now = datetime(2015, 9, 17, 2, 53, 46, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunset + 1h -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 17, 2, 53, 44, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = UTC midnight -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 17, 0, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 3
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = UTC midnight - 1s -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 23, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 4
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunrise -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 13, 33, 18, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 5
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunrise -1s -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 13, 33, 17, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = local midnight-1s -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )


async def test_if_action_after_sunrise_with_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunrise with offset.

    After sunrise is true from sunrise until midnight, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "after": SUN_EVENT_SUNRISE,
                    "after_offset": "+1:00:00",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise - 1s + 1h -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 14, 33, 17, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunrise + 1h -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 14, 33, 58, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC noon -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 12, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC noon - 1s -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 11, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local noon -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 19, 1, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local noon - 1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 18, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 3
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 1, 53, 45, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 4
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset + 1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 1, 53, 45, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 5
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight-1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-17T14:33:57.053037+00:00"},
    )


async def test_if_action_after_sunset_with_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunset with offset.

    After sunset is true from sunset until midnight, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "after": "sunset",
                    "after_offset": "+1:00:00",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunset - 1s + 1h -> 'after sunset' with offset +1h not true
    now = datetime(2015, 9, 17, 2, 53, 44, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunset + 1h -> 'after sunset' with offset +1h true
    now = datetime(2015, 9, 17, 2, 53, 45, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = midnight-1s -> 'after sunset' with offset +1h true
    now = datetime(2015, 9, 16, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T02:55:06.099767+00:00"},
    )

    # now = midnight -> 'after sunset' with offset +1h not true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-17T02:53:44.723614+00:00"},
    )


async def test_if_action_after_and_before_during(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunrise and before sunset.

    This is true from sunrise until sunset.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "after": SUN_EVENT_SUNRISE,
                    "before": SUN_EVENT_SUNSET,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise - 1s -> 'after sunrise' + 'before sunset' not true
    now = datetime(2015, 9, 16, 13, 33, 17, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": False,
            "wanted_time_before": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_after": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = sunset + 1s -> 'after sunrise' + 'before sunset' not true
    now = datetime(2015, 9, 17, 1, 53, 46, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-17T01:53:44.723614+00:00"},
    )

    # now = sunrise + 1s -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 16, 13, 33, 19, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_before": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_after": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = sunset - 1s -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 17, 1, 53, 44, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_before": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_after": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = 9AM local  -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 16, 16, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 3
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_before": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_after": "2015-09-16T13:33:18.342542+00:00",
        },
    )


async def test_if_action_before_or_after_during(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunrise or after sunset.

    This is true from midnight until sunrise and from sunset until midnight
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "before": SUN_EVENT_SUNRISE,
                    "after": SUN_EVENT_SUNSET,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise - 1s -> 'before sunrise' | 'after sunset' true
    now = datetime(2015, 9, 16, 13, 33, 17, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = sunset + 1s -> 'before sunrise' | 'after sunset' true
    now = datetime(2015, 9, 17, 1, 53, 46, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = sunrise + 1s -> 'before sunrise' | 'after sunset' false
    now = datetime(2015, 9, 16, 13, 33, 19, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": False,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = sunset - 1s -> 'before sunrise' | 'after sunset' false
    now = datetime(2015, 9, 17, 1, 53, 44, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": False,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = midnight + 1s local  -> 'before sunrise' | 'after sunset' true
    now = datetime(2015, 9, 16, 7, 0, 1, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 3
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = midnight - 1s local  -> 'before sunrise' | 'after sunset' true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 4
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )


async def test_if_action_before_sunrise_no_offset_kotzebue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    After sunrise is true from sunrise until midnight, local time.
    """
    await hass.config.async_set_time_zone("America/Anchorage")
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "before": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunrise + 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 15, 21, 13, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = sunrise - 1h -> 'before sunrise' true
    now = datetime(2015, 7, 24, 14, 21, 12, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 7, 24, 8, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-23T15:12:19.155123+00:00"},
    )


async def test_if_action_after_sunrise_no_offset_kotzebue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    Before sunrise is true from midnight until sunrise, local time.
    """
    await hass.config.async_set_time_zone("America/Anchorage")
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "after": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunrise -> 'after sunrise' true
    now = datetime(2015, 7, 24, 15, 21, 12, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = sunrise - 1h -> 'after sunrise' not true
    now = datetime(2015, 7, 24, 14, 21, 12, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight -> 'after sunrise' not true
    now = datetime(2015, 7, 24, 8, 0, 1, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight - 1s -> 'after sunrise' true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-23T15:12:19.155123+00:00"},
    )


async def test_if_action_before_sunset_no_offset_kotzebue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    Before sunset is true from midnight until sunset, local time.
    """
    await hass.config.async_set_time_zone("America/Anchorage")
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "before": SUN_EVENT_SUNSET},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunset + 1s -> 'before sunset' not true
    now = datetime(2015, 7, 25, 11, 13, 34, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = sunset - 1h-> 'before sunset' true
    now = datetime(2015, 7, 25, 10, 13, 33, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 7, 24, 8, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-24T11:17:54.446913+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-23T11:22:18.467277+00:00"},
    )


async def test_if_action_after_sunset_no_offset_kotzebue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    After sunset is true from sunset until midnight, local time.
    """
    await hass.config.async_set_time_zone("America/Anchorage")
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "after": SUN_EVENT_SUNSET},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunset -> 'after sunset' true
    now = datetime(2015, 7, 25, 11, 13, 33, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = sunset - 1s -> 'after sunset' not true
    now = datetime(2015, 7, 25, 11, 13, 32, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = local midnight -> 'after sunset' not true
    now = datetime(2015, 7, 24, 8, 0, 1, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-24T11:17:54.446913+00:00"},
    )

    # now = local midnight - 1s -> 'after sunset' true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-23T11:22:18.467277+00:00"},
    )


async def test_trigger(hass: HomeAssistant) -> None:
    """Test trigger condition."""
    config = {"alias": "Trigger Cond", "condition": "trigger", "id": "123456"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    assert not test(hass)
    assert not test(hass, {})
    assert not test(hass, {"other_var": "123456"})
    assert not test(hass, {"trigger": {"trigger_id": "123456"}})
    assert test(hass, {"trigger": {"id": "123456"}})


async def test_platform_async_validate_condition_config(hass: HomeAssistant) -> None:
    """Test platform.async_validate_condition_config will be called if it exists."""
    config = {CONF_DEVICE_ID: "test", CONF_DOMAIN: "test", CONF_CONDITION: "device"}
    with patch(
        "homeassistant.components.device_automation.condition.async_validate_condition_config",
        AsyncMock(),
    ) as device_automation_validate_condition_mock:
        await condition.async_validate_condition_config(hass, config)
        device_automation_validate_condition_mock.assert_awaited()


@pytest.mark.parametrize("enabled_value", [True, "{{ 1 == 1 }}"])
async def test_enabled_condition(
    hass: HomeAssistant, enabled_value: bool | str
) -> None:
    """Test an explicitly enabled condition."""
    config = {
        "enabled": enabled_value,
        "condition": "state",
        "entity_id": "binary_sensor.test",
        "state": "on",
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("binary_sensor.test", "on")
    assert test(hass) is True

    # Still passes, condition is not enabled
    hass.states.async_set("binary_sensor.test", "off")
    assert test(hass) is False


@pytest.mark.parametrize("enabled_value", [False, "{{ 1 == 9 }}"])
async def test_disabled_condition(
    hass: HomeAssistant, enabled_value: bool | str
) -> None:
    """Test a disabled condition returns none."""
    config = {
        "enabled": enabled_value,
        "condition": "state",
        "entity_id": "binary_sensor.test",
        "state": "on",
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("binary_sensor.test", "on")
    assert test(hass) is None

    # Still passes, condition is not enabled
    hass.states.async_set("binary_sensor.test", "off")
    assert test(hass) is None


async def test_condition_enabled_template_limited(hass: HomeAssistant) -> None:
    """Test conditions enabled template raises for non-limited template uses."""
    config = {
        "enabled": "{{ states('sensor.limited') }}",
        "condition": "state",
        "entity_id": "binary_sensor.test",
        "state": "on",
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)

    with pytest.raises(HomeAssistantError):
        await condition.async_from_config(hass, config)


async def test_and_condition_with_disabled_condition(hass: HomeAssistant) -> None:
    """Test the 'and' condition with one of the conditions disabled."""
    config = {
        "alias": "And Condition",
        "condition": "and",
        "conditions": [
            {
                "enabled": False,
                "condition": "state",
                "entity_id": "sensor.temperature",
                "state": "100",
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 110,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [{"result": {"result": None}}],
            "conditions/1": [{"result": {"result": False}}],
            "conditions/1/entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "wanted_state_below": 110.0,
                        "state": 120.0,
                    }
                }
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 105)
    assert test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": None}}],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 105.0}}],
        }
    )

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": None}}],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 100.0}}],
        }
    )


async def test_or_condition_with_disabled_condition(hass: HomeAssistant) -> None:
    """Test the 'or' condition with one of the conditions disabled."""
    config = {
        "alias": "Or Condition",
        "condition": "or",
        "conditions": [
            {
                "enabled": False,
                "condition": "state",
                "entity_id": "sensor.temperature",
                "state": "100",
            },
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": 110,
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [{"result": {"result": None}}],
            "conditions/1": [{"result": {"result": False}}],
            "conditions/1/entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "state": 120.0,
                        "wanted_state_below": 110.0,
                    }
                }
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 105)
    assert test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": None}}],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 105.0}}],
        }
    )

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": None}}],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 100.0}}],
        }
    )
