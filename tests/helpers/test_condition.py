"""Test the condition helper."""

from datetime import timedelta
import io
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from freezegun import freeze_time
import pytest
from pytest_unordered import unordered
import voluptuous as vol

from homeassistant.components.device_automation import (
    DOMAIN as DOMAIN_DEVICE_AUTOMATION,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sun import DOMAIN as DOMAIN_SUN
from homeassistant.components.system_health import DOMAIN as DOMAIN_SYSTEM_HEALTH
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConditionError, HomeAssistantError
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    entity_registry as er,
    trace,
)
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import Integration, async_get_integration
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml.loader import parse_yaml

from tests.common import MockModule, MockPlatform, mock_integration, mock_platform


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


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"condition": 123},
            "Unexpected value for condition: '123'. Expected a condition, "
            "a list of conditions or a valid template",
        )
    ],
)
async def test_invalid_condition(hass: HomeAssistant, config: dict, error: str) -> None:
    """Test if validating an invalid condition raises."""
    with pytest.raises(vol.Invalid, match=error):
        cv.CONDITION_SCHEMA(config)


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
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
            'Invalid condition "invalid" specified',
        )
    ],
)
async def test_unknown_condition(hass: HomeAssistant, config: dict, error: str) -> None:
    """Test if creating an unknown condition raises."""
    config = cv.CONDITION_SCHEMA(config)
    with pytest.raises(HomeAssistantError, match=error):
        await condition.async_from_config(hass, config)


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


async def test_time_using_time(hass: HomeAssistant) -> None:
    """Test time conditions using time entities."""
    hass.states.async_set(
        "time.am",
        "06:00:00",  # 6 am local time
    )
    hass.states.async_set(
        "time.pm",
        "18:00:00",  # 6 pm local time
    )
    hass.states.async_set(
        "time.unknown_state",
        STATE_UNKNOWN,
    )
    hass.states.async_set(
        "time.unavailable_state",
        STATE_UNAVAILABLE,
    )

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=3),
    ):
        assert not condition.time(hass, after="time.am", before="time.pm")
        assert condition.time(hass, after="time.pm", before="time.am")

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=9),
    ):
        assert condition.time(hass, after="time.am", before="time.pm")
        assert not condition.time(hass, after="time.pm", before="time.am")

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=15),
    ):
        assert condition.time(hass, after="time.am", before="time.pm")
        assert not condition.time(hass, after="time.pm", before="time.am")

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=21),
    ):
        assert not condition.time(hass, after="time.am", before="time.pm")
        assert condition.time(hass, after="time.pm", before="time.am")

    # Trigger on PM time
    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=18, minute=0, second=0),
    ):
        assert condition.time(hass, after="time.pm", before="time.am")
        assert not condition.time(hass, after="time.am", before="time.pm")
        assert condition.time(hass, after="time.pm")
        assert not condition.time(hass, before="time.pm")

    # Trigger on AM time
    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=6, minute=0, second=0),
    ):
        assert not condition.time(hass, after="time.pm", before="time.am")
        assert condition.time(hass, after="time.am", before="time.pm")
        assert condition.time(hass, after="time.am")
        assert not condition.time(hass, before="time.am")

    assert not condition.time(hass, after="time.unknown_state")
    assert not condition.time(hass, before="time.unavailable_state")

    with pytest.raises(ConditionError):
        condition.time(hass, after="time.not_existing")

    with pytest.raises(ConditionError):
        condition.time(hass, before="time.not_existing")


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


@pytest.mark.usefixtures("hass")
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


@pytest.mark.usefixtures("hass")
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


async def test_platform_async_get_conditions(hass: HomeAssistant) -> None:
    """Test platform.async_get_conditions will be called if it exists."""
    config = {CONF_DEVICE_ID: "test", CONF_DOMAIN: "test", CONF_CONDITION: "device"}
    with patch(
        "homeassistant.components.device_automation.condition.async_get_conditions",
        AsyncMock(return_value={"_device": AsyncMock()}),
    ) as device_automation_async_get_conditions_mock:
        await condition.async_validate_condition_config(hass, config)
        device_automation_async_get_conditions_mock.assert_awaited()


async def test_platform_multiple_conditions(hass: HomeAssistant) -> None:
    """Test a condition platform with multiple conditions."""

    class MockCondition(condition.Condition):
        """Mock condition."""

        def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
            """Initialize condition."""

        @classmethod
        async def async_validate_config(
            cls, hass: HomeAssistant, config: ConfigType
        ) -> ConfigType:
            """Validate config."""
            return config

    class MockCondition1(MockCondition):
        """Mock condition 1."""

        async def async_get_checker(self) -> condition.ConditionCheckerType:
            """Evaluate state based on configuration."""
            return lambda hass, vars: True

    class MockCondition2(MockCondition):
        """Mock condition 2."""

        async def async_get_checker(self) -> condition.ConditionCheckerType:
            """Evaluate state based on configuration."""
            return lambda hass, vars: False

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[condition.Condition]]:
        return {
            "_": MockCondition1,
            "cond_2": MockCondition2,
        }

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    config_1 = {CONF_CONDITION: "test"}
    config_2 = {CONF_CONDITION: "test.cond_2"}
    config_3 = {CONF_CONDITION: "test.unknown_cond"}
    assert await condition.async_validate_condition_config(hass, config_1) == config_1
    assert await condition.async_validate_condition_config(hass, config_2) == config_2
    with pytest.raises(
        vol.Invalid, match="Invalid condition 'test.unknown_cond' specified"
    ):
        await condition.async_validate_condition_config(hass, config_3)

    cond_func = await condition.async_from_config(hass, config_1)
    assert cond_func(hass, {}) is True

    cond_func = await condition.async_from_config(hass, config_2)
    assert cond_func(hass, {}) is False

    with pytest.raises(KeyError):
        await condition.async_from_config(hass, config_3)


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


@pytest.mark.parametrize(
    "sun_condition_descriptions",
    [
        """
        _:
          fields:
            after:
              example: sunrise
              selector:
                select:
                  options:
                    - sunrise
                    - sunset
            after_offset:
              selector:
                time: null
            before:
              example: sunrise
              selector:
                select:
                  options:
                    - sunrise
                    - sunset
            before_offset:
              selector:
                time: null
        """,
        """
        .sunrise_sunset_selector: &sunrise_sunset_selector
          example: sunrise
          selector:
            select:
              options:
                - sunrise
                - sunset
        .offset_selector: &offset_selector
          selector:
            time: null
        _:
          fields:
            after: *sunrise_sunset_selector
            after_offset: *offset_selector
            before: *sunrise_sunset_selector
            before_offset: *offset_selector
        """,
    ],
)
async def test_async_get_all_descriptions(
    hass: HomeAssistant, sun_condition_descriptions: str
) -> None:
    """Test async_get_all_descriptions."""
    device_automation_condition_descriptions = """
        _device:
          fields:
            entity:
              selector:
                entity:
                  filter:
                    domain: alarm_control_panel
                    supported_features:
                      - alarm_control_panel.AlarmControlPanelEntityFeature.ARM_HOME
        """

    assert await async_setup_component(hass, DOMAIN_SUN, {})
    assert await async_setup_component(hass, DOMAIN_SYSTEM_HEALTH, {})
    await hass.async_block_till_done()

    def _load_yaml(fname, secrets=None):
        if fname.endswith("device_automation/conditions.yaml"):
            condition_descriptions = device_automation_condition_descriptions
        elif fname.endswith("sun/conditions.yaml"):
            condition_descriptions = sun_condition_descriptions
        with io.StringIO(condition_descriptions) as file:
            return parse_yaml(file)

    with (
        patch(
            "homeassistant.helpers.condition._load_conditions_files",
            side_effect=condition._load_conditions_files,
        ) as proxy_load_conditions_files,
        patch(
            "annotatedyaml.loader.load_yaml",
            side_effect=_load_yaml,
        ),
        patch.object(Integration, "has_conditions", return_value=True),
    ):
        descriptions = await condition.async_get_all_descriptions(hass)

    # Test we only load conditions.yaml for integrations with conditions,
    # system_health has no conditions
    assert proxy_load_conditions_files.mock_calls[0][1][0] == unordered(
        [
            await async_get_integration(hass, DOMAIN_SUN),
        ]
    )

    # system_health does not have conditions and should not be in descriptions
    assert descriptions == {
        "sun": {
            "fields": {
                "after": {
                    "example": "sunrise",
                    "selector": {
                        "select": {
                            "custom_value": False,
                            "multiple": False,
                            "options": ["sunrise", "sunset"],
                            "sort": False,
                        }
                    },
                },
                "after_offset": {"selector": {"time": {}}},
                "before": {
                    "example": "sunrise",
                    "selector": {
                        "select": {
                            "custom_value": False,
                            "multiple": False,
                            "options": ["sunrise", "sunset"],
                            "sort": False,
                        }
                    },
                },
                "before_offset": {"selector": {"time": {}}},
            }
        }
    }

    # Verify the cache returns the same object
    assert await condition.async_get_all_descriptions(hass) is descriptions

    # Load the device_automation integration and check a new cache object is created
    assert await async_setup_component(hass, DOMAIN_DEVICE_AUTOMATION, {})
    await hass.async_block_till_done()

    with (
        patch(
            "annotatedyaml.loader.load_yaml",
            side_effect=_load_yaml,
        ),
        patch.object(Integration, "has_conditions", return_value=True),
    ):
        new_descriptions = await condition.async_get_all_descriptions(hass)
    assert new_descriptions is not descriptions
    assert new_descriptions == {
        "sun": {
            "fields": {
                "after": {
                    "example": "sunrise",
                    "selector": {
                        "select": {
                            "custom_value": False,
                            "multiple": False,
                            "options": ["sunrise", "sunset"],
                            "sort": False,
                        }
                    },
                },
                "after_offset": {"selector": {"time": {}}},
                "before": {
                    "example": "sunrise",
                    "selector": {
                        "select": {
                            "custom_value": False,
                            "multiple": False,
                            "options": ["sunrise", "sunset"],
                            "sort": False,
                        }
                    },
                },
                "before_offset": {"selector": {"time": {}}},
            }
        },
        "device": {
            "fields": {
                "entity": {
                    "selector": {
                        "entity": {
                            "filter": [
                                {
                                    "domain": ["alarm_control_panel"],
                                    "supported_features": [1],
                                }
                            ],
                            "multiple": False,
                            "reorder": False,
                        },
                    },
                },
            }
        },
    }

    # Verify the cache returns the same object
    assert await condition.async_get_all_descriptions(hass) is new_descriptions


@pytest.mark.parametrize(
    ("yaml_error", "expected_message"),
    [
        (
            FileNotFoundError("Blah"),
            "Unable to find conditions.yaml for the sun integration",
        ),
        (
            HomeAssistantError("Test error"),
            "Unable to parse conditions.yaml for the sun integration: Test error",
        ),
    ],
)
async def test_async_get_all_descriptions_with_yaml_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    yaml_error: Exception,
    expected_message: str,
) -> None:
    """Test async_get_all_descriptions."""
    assert await async_setup_component(hass, DOMAIN_SUN, {})
    await hass.async_block_till_done()

    def _load_yaml_dict(fname, secrets=None):
        raise yaml_error

    with (
        patch(
            "homeassistant.helpers.condition.load_yaml_dict",
            side_effect=_load_yaml_dict,
        ),
        patch.object(Integration, "has_conditions", return_value=True),
    ):
        descriptions = await condition.async_get_all_descriptions(hass)

    assert descriptions == {DOMAIN_SUN: None}

    assert expected_message in caplog.text


async def test_async_get_all_descriptions_with_bad_description(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_get_all_descriptions."""
    sun_service_descriptions = """
        _:
          fields: not_a_dict
    """

    assert await async_setup_component(hass, DOMAIN_SUN, {})
    await hass.async_block_till_done()

    def _load_yaml(fname, secrets=None):
        with io.StringIO(sun_service_descriptions) as file:
            return parse_yaml(file)

    with (
        patch(
            "annotatedyaml.loader.load_yaml",
            side_effect=_load_yaml,
        ),
        patch.object(Integration, "has_conditions", return_value=True),
    ):
        descriptions = await condition.async_get_all_descriptions(hass)

    assert descriptions == {"sun": None}

    assert (
        "Unable to parse conditions.yaml for the sun integration: "
        "expected a dictionary for dictionary value @ data['_']['fields']"
    ) in caplog.text


async def test_invalid_condition_platform(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid condition platform."""
    mock_integration(hass, MockModule("test", async_setup=AsyncMock(return_value=True)))
    mock_platform(hass, "test.condition", MockPlatform())

    await async_setup_component(hass, "test", {})

    assert (
        "Integration test does not provide condition support, skipping" in caplog.text
    )


@patch("annotatedyaml.loader.load_yaml")
@patch.object(Integration, "has_conditions", return_value=True)
async def test_subscribe_conditions(
    mock_has_conditions: Mock,
    mock_load_yaml: Mock,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test condition.async_subscribe_platform_events."""
    sun_condition_descriptions = """
        sun: {}
        """

    def _load_yaml(fname, secrets=None):
        if fname.endswith("sun/conditions.yaml"):
            condition_descriptions = sun_condition_descriptions
        else:
            raise FileNotFoundError
        with io.StringIO(condition_descriptions) as file:
            return parse_yaml(file)

    mock_load_yaml.side_effect = _load_yaml

    async def broken_subscriber(_):
        """Simulate a broken subscriber."""
        raise Exception("Boom!")  # noqa: TRY002

    condition_events = []

    async def good_subscriber(new_conditions: set[str]):
        """Simulate a working subscriber."""
        condition_events.append(new_conditions)

    condition.async_subscribe_platform_events(hass, broken_subscriber)
    condition.async_subscribe_platform_events(hass, good_subscriber)

    assert await async_setup_component(hass, "sun", {})

    assert condition_events == [{"sun"}]
    assert "Error while notifying condition platform listener" in caplog.text
