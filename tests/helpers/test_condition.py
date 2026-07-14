"""Test the condition helper."""

import asyncio
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, nullcontext as does_not_raise
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import io
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_unordered import unordered
from sqlalchemy.exc import SQLAlchemyError
import voluptuous as vol

from homeassistant.components.device_automation import (
    DOMAIN as DEVICE_AUTOMATION_DOMAIN,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.recorder import Recorder, get_instance, history
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sun import DOMAIN as SUN_DOMAIN
from homeassistant.components.system_health import DOMAIN as SYSTEM_HEALTH_DOMAIN
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_CLASS,
    ATTR_LABEL_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ConditionError, HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    condition,
    config_validation as cv,
    entity_registry as er,
    label_registry as lr,
    trace,
)
from homeassistant.helpers.automation import (
    DomainSpec,
    move_top_level_schema_fields_to_options,
)
from homeassistant.helpers.condition import (
    _DATA_HISTORY_PRIMING_MANAGER,
    ATTR_BEHAVIOR,
    BEHAVIOR_ALL,
    BEHAVIOR_ANY,
    CONDITIONS,
    MAX_HISTORY_PRIMING_LOOKBACK,
    Condition,
    ConditionChecker,
    EntityConditionBase,
    EntityNumericalConditionWithUnitBase,
    _async_get_condition_platform,
    _HistoryPrimingManager,
    async_validate_condition_config,
    make_entity_numerical_condition,
    make_entity_numerical_condition_with_unit,
    make_entity_state_condition,
)
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType
from homeassistant.loader import Integration, async_get_integration
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter
from homeassistant.util.yaml.loader import parse_yaml

from tests.common import MockModule, MockPlatform, mock_integration, mock_platform
from tests.components.recorder.common import async_wait_recording_done


async def _create_primary_and_diagnostic_entities_in_area(
    hass: HomeAssistant, domain: str
) -> tuple[str, str, str]:
    """Create a primary and a diagnostic entity in the same area.

    Returns a tuple of (area_id, primary_entity_id, diagnostic_entity_id).
    """
    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Test Area")

    entity_reg = er.async_get(hass)
    primary = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_primary",
        suggested_object_id=f"primary_{domain}",
    )
    entity_reg.async_update_entity(primary.entity_id, area_id=area.id)
    diagnostic = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_diagnostic",
        suggested_object_id=f"diagnostic_{domain}",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    entity_reg.async_update_entity(diagnostic.entity_id, area_id=area.id)
    return area.id, primary.entity_id, diagnostic.entity_id


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
            {"blabla": "not_a_condition"},
            "Unexpected value for condition: 'None'. Expected a condition, "
            "a list of conditions or a valid template",
        ),
        (
            {"condition": 123},
            "Unexpected value for condition: '123'. Expected a condition, "
            "a list of conditions or a valid template",
        ),
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
        test.async_check()
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
    assert not test.async_check()
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
    assert not test.async_check()
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
    assert test.async_check()
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
        test.async_check()
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
        test.async_check()
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
    assert not test.async_check()
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
    assert not test.async_check()
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [
                {"result": {"entities": ["sensor.temperature"], "result": False}}
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 105)
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100)
    assert test.async_check()


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
    assert not test.async_check()
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [
                {"result": {"entities": ["sensor.temperature"], "result": False}}
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 105)
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100)
    assert test.async_check()


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
    assert not test.async_check()
    assert_condition_trace(
        {
            "": [{"result": {"result": False}}],
            "conditions/0": [
                {"result": {"entities": ["sensor.temperature"], "result": False}}
            ],
        }
    )

    hass.states.async_set("sensor.temperature", 105)
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100)
    assert test.async_check()


async def test_conditions_from_config_has_and_semantics(
    hass: HomeAssistant,
) -> None:
    """Test that async_conditions_from_config returns a callable with AND semantics."""
    hass.states.async_set("binary_sensor.test_one", STATE_ON)
    hass.states.async_set("binary_sensor.test_two", STATE_ON)
    configs = await condition.async_validate_conditions_config(
        hass,
        [
            {
                "condition": "state",
                "entity_id": "binary_sensor.test_one",
                "state": STATE_ON,
            },
            {
                "condition": "state",
                "entity_id": "binary_sensor.test_two",
                "state": STATE_ON,
            },
        ],
    )
    test = await condition.async_conditions_from_config(
        hass, configs, logging.getLogger(__name__), "test"
    )
    assert test.async_check() is True
    hass.states.async_set("binary_sensor.test_two", STATE_OFF)
    assert test.async_check() is False


async def test_conditions_from_config_forwards_call(
    hass: HomeAssistant,
) -> None:
    """Test that async_conditions_from_config forwards call."""
    hass.states.async_set("binary_sensor.test_one", STATE_ON)
    hass.states.async_set("binary_sensor.test_two", STATE_ON)
    configs = await condition.async_validate_conditions_config(
        hass,
        [
            {
                "condition": "state",
                "entity_id": "binary_sensor.test_one",
                "state": STATE_ON,
            },
            {
                "condition": "state",
                "entity_id": "binary_sensor.test_two",
                "state": STATE_ON,
            },
        ],
    )
    test = await condition.async_conditions_from_config(
        hass, configs, logging.getLogger(__name__), "test"
    )
    assert test() is True
    hass.states.async_set("binary_sensor.test_two", STATE_OFF)
    assert test() is False


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
        test.async_check()
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
    assert not test.async_check()
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
    assert test.async_check()
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
    assert test.async_check()
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
        test.async_check()
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
        test.async_check()
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
    assert test.async_check()
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
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 105)
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 100)
    assert test.async_check()


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
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 105)
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 100)
    assert test.async_check()


async def test_shorthand_template_condition_in_or(hass: HomeAssistant) -> None:
    """Test shorthand template condition inside or block doesn't crash."""
    config = {
        "condition": "or",
        "conditions": [
            '{{ states("sensor.test") == "on" }}',
            {"condition": "state", "entity_id": "sensor.other", "state": "on"},
        ],
    }
    config = await condition.async_validate_condition_config(hass, config)
    assert config["conditions"][0]["condition"] == "template"

    # Verify the condition can actually be evaluated at runtime
    test = await condition.async_from_config(hass, config)
    hass.states.async_set("sensor.test", "on")
    hass.states.async_set("sensor.other", "off")
    assert test.async_check()


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
        test.async_check()
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
    assert test.async_check()
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
    assert test.async_check()
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
    assert not test.async_check()
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
    assert not test.async_check()
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
        test.async_check()
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
        test.async_check()
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
    assert not test.async_check()
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
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 50)
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 49)
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100)
    assert not test.async_check()


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
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 50)
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 49)
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100)
    assert not test.async_check()


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
        assert not test1.async_check()
        assert test2.async_check()

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=9),
    ):
        assert test1.async_check()
        assert not test2.async_check()

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=15),
    ):
        assert test1.async_check()
        assert not test2.async_check()

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt_util.now().replace(hour=21),
    ):
        assert not test1.async_check()
        assert test2.async_check()


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
        "sensor.uptime_am",
        "2021-06-03 13:00:00.000000+00:00",  # 6 am local time
        {ATTR_DEVICE_CLASS: SensorDeviceClass.UPTIME},
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
        assert condition.time(hass, after="sensor.uptime_am", before="sensor.pm")
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
        test.async_check()
    with pytest.raises(ConditionError, match="unknown entity.*window"):
        test.async_check()

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
        test.async_check()


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
    assert not test.async_check()

    now = dt_util.utcnow() + timedelta(seconds=5)
    with freeze_time(now):
        assert test.async_check()


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
    assert not test.async_check()

    now = dt_util.utcnow() + timedelta(seconds=5)
    with freeze_time(now):
        assert test.async_check()


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
        assert not test.async_check()


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
    assert not test.async_check()
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
    assert test.async_check()

    hass.states.async_set("sensor.temperature_1", 101)
    hass.states.async_set("sensor.temperature_2", 100)
    assert not test.async_check()

    hass.states.async_set("sensor.temperature_1", 100)
    hass.states.async_set("sensor.temperature_2", 101)
    assert not test.async_check()


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
    assert test.async_check()

    hass.states.async_set("sensor.temperature_1", 101)
    hass.states.async_set("sensor.temperature_2", 100)
    assert test.async_check()

    hass.states.async_set("sensor.temperature_1", 100)
    hass.states.async_set("sensor.temperature_2", 101)
    assert test.async_check()

    hass.states.async_set("sensor.temperature_1", 101)
    hass.states.async_set("sensor.temperature_2", 101)
    assert not test.async_check()


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
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 200)
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 42)
    assert not test.async_check()


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
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 200})
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 100, {"attribute1": "200"})
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 201})
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100, {"attribute1": None})
    assert not test.async_check()


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
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100, {"happening": True})
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100, {"no_happening": 201})
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100, {"happening": False})
    assert test.async_check()


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
    assert test.async_check()

    hass.states.async_set("switch.test", "off")
    assert not test.async_check()


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
    assert test.async_check()

    hass.states.async_set("sensor.salut", "salut")
    assert test.async_check()

    hass.states.async_set("sensor.salut", "hello")
    assert not test.async_check()

    await hass.services.async_call(
        "input_text",
        "set_value",
        {
            "entity_id": "input_text.hello",
            "value": "hi",
        },
        blocking=True,
    )
    assert not test.async_check()

    hass.states.async_set("sensor.salut", "hi")
    assert test.async_check()

    hass.states.async_set("sensor.salut", "cya")
    assert test.async_check()

    await hass.services.async_call(
        "input_select",
        "select_option",
        {
            "entity_id": "input_select.hello",
            "option": "welcome",
        },
        blocking=True,
    )
    assert not test.async_check()

    hass.states.async_set("sensor.salut", "welcome")
    assert test.async_check()


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
    assert not test.async_check()

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
    assert not test.async_check()

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
        test.async_check()
    with pytest.raises(ConditionError, match="unknown entity.*humidity"):
        test.async_check()

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
        test.async_check()

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
        test.async_check()

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
        test.async_check()

    # Below entity not a number
    hass.states.async_set("input_number.missing", "number")
    with pytest.raises(
        ConditionError,
        match="'below'.*input_number.missing.*cannot be processed as a number",
    ):
        test.async_check()

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
        test.async_check()

    # Above entity not a number
    hass.states.async_set("input_number.missing", "number")
    with pytest.raises(
        ConditionError,
        match="'above'.*input_number.missing.*cannot be processed as a number",
    ):
        test.async_check()


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
    assert not test.async_check()
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
    assert test.async_check()

    hass.states.async_set("sensor.temperature_1", 50)
    hass.states.async_set("sensor.temperature_2", 49)
    assert not test.async_check()

    hass.states.async_set("sensor.temperature_1", 49)
    hass.states.async_set("sensor.temperature_2", 50)
    assert not test.async_check()


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
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 49})
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 100, {"attribute1": "49"})
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 51})
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100, {"attribute1": None})
    assert not test.async_check()


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
    assert test.async_check()

    hass.states.async_set("sensor.test", "90")
    assert not test.async_check()


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
    assert test.async_check()

    hass.states.async_set("sensor.temperature", 10)
    assert not test.async_check()

    hass.states.async_set("sensor.temperature", 100)
    assert not test.async_check()

    hass.states.async_set("input_number.high", "unknown")
    assert not test.async_check()

    hass.states.async_set("input_number.high", "unavailable")
    assert not test.async_check()

    await hass.services.async_call(
        "input_number",
        "set_value",
        {
            "entity_id": "input_number.high",
            "value": 101,
        },
        blocking=True,
    )
    assert test.async_check()

    hass.states.async_set("number.low", "unknown")
    assert not test.async_check()

    hass.states.async_set("number.low", "unavailable")
    assert not test.async_check()

    with pytest.raises(ConditionError):
        condition.async_numeric_state(
            hass, entity="sensor.temperature", below="input_number.not_exist"
        )
    with pytest.raises(ConditionError):
        condition.async_numeric_state(
            hass, entity="sensor.temperature", above="input_number.not_exist"
        )


async def test_extract_entities(hass: HomeAssistant) -> None:
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
                {
                    "condition": "zone",
                    "options": {
                        "entity_id": [
                            "device_tracker.paulus",
                            "device_tracker.anne_therese",
                        ],
                        "zone": ["zone.home"],
                    },
                },
                {
                    "condition": "zone.in_zone",
                    "target": {"entity_id": "person.paulus"},
                    "options": {"zone": "zone.work", "behavior": "any"},
                },
                {
                    "condition": "zone.occupancy_is_detected",
                    "options": {"zone": "zone.school"},
                },
                {
                    "condition": "time",
                    "after": "input_datetime.start",
                    "before": "sensor.end",
                },
                {
                    "condition": "time",
                    "after": "08:00:00",
                },
                Template("{{ is_state('light.example', 'on') }}", hass),
            ],
        }
    ) == {
        "device_tracker.anne_therese",
        "device_tracker.paulus",
        "input_datetime.start",
        "person.paulus",
        "sensor.end",
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
        "zone.home",
        "zone.school",
        "zone.work",
    }


async def test_extract_entities_zone_condition_validated(hass: HomeAssistant) -> None:
    """Test extracting entities from a validated legacy zone condition.

    Validation moves the top level entity_id and zone fields into options.
    """
    assert await async_setup_component(hass, "zone", {})
    config = await condition.async_validate_condition_config(
        hass,
        {
            "condition": "zone",
            "entity_id": "device_tracker.paulus",
            "zone": "zone.home",
        },
    )
    assert condition.async_extract_entities(config) == {
        "device_tracker.paulus",
        "zone.home",
    }


async def test_extract_devices(hass: HomeAssistant) -> None:
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
                Template("{{ is_state('light.example', 'on') }}", hass),
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
        test.async_check()


@pytest.mark.parametrize(
    ("value_template", "expectation", "expected_template_errors", "expected_result"),
    [
        # Undefined variable used in a way that raises (e.g. attribute access)
        (
            "{{ trigger.to_state.attributes.event_type == 'double_press' }}",
            pytest.raises(ConditionError),
            ["'trigger' is undefined"],
            {},
        ),
        # Undefined variable used in a way that only warns
        (
            "{{ no_such_variable }}",
            does_not_raise(),
            ["'no_such_variable' is undefined"],
            {"result": False, "entities": []},
        ),
        # A single render can emit more than one message
        (
            "{{ foo }}{{ bar }}",
            does_not_raise(),
            ["'foo' is undefined", "'bar' is undefined"],
            {"result": False, "entities": []},
        ),
    ],
)
async def test_condition_template_error_traced_not_logged(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    value_template: str,
    expectation: AbstractContextManager,
    expected_template_errors: list[str],
    expected_result: dict[str, Any],
) -> None:
    """Test template errors are added to the trace and not logged when opted in.

    The subscribe_condition websocket command re-evaluates a condition every
    second and opts in via trace.suppress_template_error_logging(). Template
    variable errors are then recorded in the trace without being logged.
    """
    caplog.set_level(logging.WARNING)
    config = {"condition": "template", "value_template": value_template}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    with expectation, trace.suppress_template_error_logging():
        test.async_check()

    # The template errors are recorded in the trace...
    condition_trace = trace.trace_get(clear=False)
    trace.trace_clear()
    trace_element = condition_trace[""][0]
    assert trace_element.template_errors == expected_template_errors
    assert (trace_element._result or {}) == expected_result

    # ...and not logged
    assert "Template variable" not in caplog.text


async def test_condition_template_error_logged_without_opt_in(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test template errors are logged when suppression is not opted in.

    The error is always recorded in the trace, but unless the consumer opts in
    via trace.suppress_template_error_logging() it is also logged as usual.
    """
    caplog.set_level(logging.WARNING)
    config = {"condition": "template", "value_template": "{{ no_such_variable }}"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    assert test.async_check() is False

    # Recorded in the trace...
    condition_trace = trace.trace_get(clear=False)
    trace.trace_clear()
    assert condition_trace[""][0].template_errors == ["'no_such_variable' is undefined"]

    # ...and also logged
    assert "Template variable warning: 'no_such_variable' is undefined" in caplog.text


async def test_condition_template_invalid_results(hass: HomeAssistant) -> None:
    """Test template condition render false with invalid results."""
    config = {"condition": "template", "value_template": "{{ 'string' }}"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert not test.async_check()

    config = {"condition": "template", "value_template": "{{ 10.1 }}"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert not test.async_check()

    config = {"condition": "template", "value_template": "{{ 42 }}"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert not test.async_check()

    config = {"condition": "template", "value_template": "{{ [1, 2, 3] }}"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert not test.async_check()


async def test_trigger(hass: HomeAssistant) -> None:
    """Test trigger condition."""
    config = {"alias": "Trigger Cond", "condition": "trigger", "id": "123456"}
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    assert not test.async_check()
    assert not test.async_check(variables={})
    assert not test.async_check(variables={"other_var": "123456"})
    assert not test.async_check(variables={"trigger": {"trigger_id": "123456"}})
    assert test.async_check(variables={"trigger": {"id": "123456"}})


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

    class MockCondition(Condition):
        """Mock condition."""

        @classmethod
        async def async_validate_config(
            cls, hass: HomeAssistant, config: ConfigType
        ) -> ConfigType:
            """Validate config."""
            return config

    class MockCondition1(MockCondition):
        """Mock condition 1."""

        def _async_check(self, **kwargs) -> bool:
            """Check the condition."""
            return True

    class MockCondition2(MockCondition):
        """Mock condition 2."""

        def _async_check(self, **kwargs) -> bool:
            """Check the condition."""
            return False

    async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
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
    assert await async_validate_condition_config(hass, config_1) == config_1
    assert await async_validate_condition_config(hass, config_2) == config_2
    with pytest.raises(
        vol.Invalid, match="Invalid condition 'test.unknown_cond' specified"
    ):
        await async_validate_condition_config(hass, config_3)

    cond = await condition.async_from_config(hass, config_1)
    assert cond.async_check(variables={}) is True

    cond = await condition.async_from_config(hass, config_2)
    assert cond.async_check(variables={}) is False

    with pytest.raises(KeyError):
        await condition.async_from_config(hass, config_3)


async def test_platform_migrate_condition(hass: HomeAssistant) -> None:
    """Test a condition platform with a migration."""

    OPTIONS_SCHEMA_DICT = {
        vol.Required("option_1"): str,
        vol.Optional("option_2"): int,
    }

    class MockCondition(Condition):
        """Mock condition."""

        @classmethod
        async def async_validate_complete_config(
            cls, hass: HomeAssistant, complete_config: ConfigType
        ) -> ConfigType:
            """Validate complete config."""
            complete_config = move_top_level_schema_fields_to_options(
                complete_config, OPTIONS_SCHEMA_DICT
            )
            return await super().async_validate_complete_config(hass, complete_config)

        @classmethod
        async def async_validate_config(
            cls, hass: HomeAssistant, config: ConfigType
        ) -> ConfigType:
            """Validate config."""
            return config

    async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
        return {
            "_": MockCondition,
        }

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    config_1 = {
        "condition": "test",
        "option_1": "value_1",
        "option_2": 2,
    }
    config_2 = {
        "condition": "test",
        "option_1": "value_1",
    }
    config_1_migrated = {
        "condition": "test",
        "options": {"option_1": "value_1", "option_2": 2},
    }
    config_2_migrated = {
        "condition": "test",
        "options": {"option_1": "value_1"},
    }

    assert await async_validate_condition_config(hass, config_1) == config_1_migrated
    assert await async_validate_condition_config(hass, config_2) == config_2_migrated
    assert (
        await async_validate_condition_config(hass, config_1_migrated)
        == config_1_migrated
    )
    assert (
        await async_validate_condition_config(hass, config_2_migrated)
        == config_2_migrated
    )


async def test_platform_backwards_compatibility_for_new_style_configs(
    hass: HomeAssistant,
) -> None:
    """Test backwards compatibility for old-style conditions with new-style configs."""
    config_old_style = {
        "condition": "numeric_state",
        "entity_id": ["sensor.test"],
        "above": 50,
    }
    result = await async_validate_condition_config(hass, config_old_style)
    assert result == config_old_style

    config_new_style = {
        "condition": "numeric_state",
        "options": {
            "entity_id": ["sensor.test"],
            "above": 50,
        },
    }
    result = await async_validate_condition_config(hass, config_new_style)
    assert result == config_old_style


async def test_get_condition_platform_registers_conditions(
    hass: HomeAssistant,
) -> None:
    """Test _async_get_condition_platform registers and notifies."""

    class MockCondition(Condition):
        """Mock condition."""

        @classmethod
        async def async_validate_config(
            cls, hass: HomeAssistant, config: ConfigType
        ) -> ConfigType:
            return config

        def _async_check(self, **kwargs) -> bool:
            """Check the condition."""
            return True

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"cond_a": MockCondition, "cond_b": MockCondition}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    subscriber_events: list[set[str]] = []

    async def subscriber(new_conditions: set[str]) -> None:
        subscriber_events.append(new_conditions)

    condition.async_subscribe_platform_events(hass, subscriber)

    assert "test.cond_a" not in hass.data[CONDITIONS]
    assert "test.cond_b" not in hass.data[CONDITIONS]

    # First call registers all conditions from the platform and notifies subscribers
    await _async_get_condition_platform(hass, "test.cond_a")

    assert hass.data[CONDITIONS]["test.cond_a"] == "test"
    assert hass.data[CONDITIONS]["test.cond_b"] == "test"
    assert len(subscriber_events) == 1
    assert subscriber_events[0] == {"test.cond_a", "test.cond_b"}

    # Subsequent calls are idempotent — no re-registration or re-notification
    await _async_get_condition_platform(hass, "test.cond_a")
    await _async_get_condition_platform(hass, "test.cond_b")
    assert len(subscriber_events) == 1


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
    assert test.async_check() is True

    # Still passes, condition is not enabled
    hass.states.async_set("binary_sensor.test", "off")
    assert test.async_check() is False


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
    assert test.async_check() is None

    # Still passes, condition is not enabled
    hass.states.async_set("binary_sensor.test", "off")
    assert test.async_check() is None


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
    assert not test.async_check()
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
    assert test.async_check()
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": None}}],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 105.0}}],
        }
    )

    hass.states.async_set("sensor.temperature", 100)
    assert test.async_check()
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
    assert not test.async_check()
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
    assert test.async_check()
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": None}}],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 105.0}}],
        }
    )

    hass.states.async_set("sensor.temperature", 100)
    assert test.async_check()
    assert_condition_trace(
        {
            "": [{"result": {"result": True}}],
            "conditions/0": [{"result": {"result": None}}],
            "conditions/1": [{"result": {"result": True}}],
            "conditions/1/entity_id/0": [{"result": {"result": True, "state": 100.0}}],
        }
    )


_MODERN_SUN_CONDITIONS = (
    "sun.elevation",
    "sun.is_ascending",
    "sun.is_descending",
    "sun.is_evening_twilight",
    "sun.is_morning_twilight",
    "sun.is_night",
    "sun.is_set",
    "sun.is_up",
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
    hass: HomeAssistant,
    sun_condition_descriptions: str,
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
    light_condition_descriptions = """
        is_off:
          target:
            entity:
              domain: light
        is_on:
          target:
            entity:
              domain: light
        is_brightness:
          target:
            entity:
              domain: light
        """

    assert await async_setup_component(hass, SUN_DOMAIN, {})
    assert await async_setup_component(hass, SYSTEM_HEALTH_DOMAIN, {})
    await hass.async_block_till_done()

    def _load_yaml(fname, secrets=None):
        if fname.endswith("device_automation/conditions.yaml"):
            condition_descriptions = device_automation_condition_descriptions
        elif fname.endswith("light/conditions.yaml"):
            condition_descriptions = light_condition_descriptions
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
            await async_get_integration(hass, SUN_DOMAIN),
        ]
    )

    # system_health does not have conditions and should not be in descriptions
    expected_descriptions = {
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
        # The modern sun conditions have no entry in the mocked conditions.yaml.
        **dict.fromkeys(_MODERN_SUN_CONDITIONS),
    }
    assert descriptions == expected_descriptions

    # Verify the cache returns the same object
    assert await condition.async_get_all_descriptions(hass) is descriptions

    # Load the device_automation integration and check a new cache object is created
    assert await async_setup_component(hass, DEVICE_AUTOMATION_DOMAIN, {})
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
    # The device automation conditions should now be present
    expected_descriptions |= {
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
    assert new_descriptions == expected_descriptions

    # Verify the cache returns the same object
    assert await condition.async_get_all_descriptions(hass) is new_descriptions

    # Load the light integration and check a new cache object is created
    assert await async_setup_component(hass, LIGHT_DOMAIN, {})
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
    # The light conditions should now be present
    assert new_descriptions == expected_descriptions | {
        "light.is_off": {
            "fields": {},
            "target": {
                "entity": [
                    {
                        "domain": [
                            "light",
                        ],
                    },
                ],
            },
        },
        "light.is_on": {
            "fields": {},
            "target": {
                "entity": [
                    {
                        "domain": [
                            "light",
                        ],
                    },
                ],
            },
        },
        "light.is_brightness": {
            "fields": {},
            "target": {
                "entity": [
                    {
                        "domain": [
                            "light",
                        ],
                    },
                ],
            },
        },
    }

    # Verify the cache returns the same object
    assert await condition.async_get_all_descriptions(hass) is new_descriptions

    await hass.data["entity_components"][SUN_DOMAIN]._async_reset()


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
    assert await async_setup_component(hass, SUN_DOMAIN, {})
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

    assert descriptions == {SUN_DOMAIN: None, **dict.fromkeys(_MODERN_SUN_CONDITIONS)}

    assert expected_message in caplog.text

    await hass.data["entity_components"][SUN_DOMAIN]._async_reset()


async def test_async_get_all_descriptions_with_bad_description(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_get_all_descriptions."""
    sun_service_descriptions = """
        _:
          fields: not_a_dict
    """

    assert await async_setup_component(hass, SUN_DOMAIN, {})
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

    assert descriptions == {"sun": None, **dict.fromkeys(_MODERN_SUN_CONDITIONS)}

    assert (
        "Unable to parse conditions.yaml for the sun integration: "
        "expected a dictionary for dictionary value @ data['_']['fields']"
    ) in caplog.text

    await hass.data["entity_components"][SUN_DOMAIN]._async_reset()


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

    assert condition_events == [{"sun", *_MODERN_SUN_CONDITIONS}]
    assert "Error while notifying condition platform listener" in caplog.text

    await hass.data["entity_components"][SUN_DOMAIN]._async_reset()


@patch("annotatedyaml.loader.load_yaml")
@patch.object(Integration, "has_conditions", return_value=True)
@patch(
    "homeassistant.components.light.condition.async_get_conditions",
    new=AsyncMock(return_value={}),
)
async def test_subscribe_conditions_no_conditions(
    mock_has_conditions: Mock,
    mock_load_yaml: Mock,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_subscribe_platform_events skips platforms without conditions."""
    # Return empty conditions.yaml for light integration, the actual condition
    # descriptions are irrelevant for this test
    light_condition_descriptions = ""

    def _load_yaml(fname, secrets=None):
        if fname.endswith("light/conditions.yaml"):
            condition_descriptions = light_condition_descriptions
        else:
            raise FileNotFoundError
        with io.StringIO(condition_descriptions) as file:
            return parse_yaml(file)

    mock_load_yaml.side_effect = _load_yaml

    condition_events = []

    async def good_subscriber(new_conditions: set[str]):
        """Simulate a working subscriber."""
        condition_events.append(new_conditions)

    condition.async_subscribe_platform_events(hass, good_subscriber)

    assert await async_setup_component(hass, "light", {})
    await hass.async_block_till_done()
    assert condition_events == []


_DEFAULT_DOMAIN_SPECS = {"test": DomainSpec()}


async def _setup_numerical_condition(
    hass: HomeAssistant,
    condition_options: dict[str, Any],
    target_config: dict[str, Any],
    domain_specs: Mapping[str, DomainSpec] | None = None,
    valid_unit: str | None | UndefinedType = UNDEFINED,
    primary_entities_only: bool = True,
) -> condition.ConditionChecker:
    """Set up a numerical condition via a mock platform and return the test."""
    condition_cls = make_entity_numerical_condition(
        domain_specs or _DEFAULT_DOMAIN_SPECS,
        valid_unit,
        primary_entities_only=primary_entities_only,
    )

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": condition_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    config: dict[str, Any] = {
        CONF_CONDITION: "test",
        CONF_TARGET: target_config,
        CONF_OPTIONS: condition_options,
    }

    config = await async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert test is not None
    return test


@pytest.mark.parametrize(
    ("condition_options", "state_value", "expected"),
    [
        # above only
        ({"threshold": {"type": "above", "value": {"number": 50}}}, "75", True),
        ({"threshold": {"type": "above", "value": {"number": 50}}}, "50", False),
        ({"threshold": {"type": "above", "value": {"number": 50}}}, "25", False),
        # below only
        ({"threshold": {"type": "below", "value": {"number": 50}}}, "25", True),
        ({"threshold": {"type": "below", "value": {"number": 50}}}, "50", False),
        ({"threshold": {"type": "below", "value": {"number": 50}}}, "75", False),
        # between (range) — limits are inclusive, so a value exactly equal
        # to either bound is treated as "inside" and matches
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 20},
                    "value_max": {"number": 80},
                }
            },
            "50",
            True,
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 20},
                    "value_max": {"number": 80},
                }
            },
            "20",
            True,
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 20},
                    "value_max": {"number": 80},
                }
            },
            "80",
            True,
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 20},
                    "value_max": {"number": 80},
                }
            },
            "10",
            False,
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 20},
                    "value_max": {"number": 80},
                }
            },
            "90",
            False,
        ),
        # outside (inverse of between) — limits are inclusive on the between
        # side, so a value exactly equal to either bound is "inside" and
        # does NOT match outside
        (
            {
                "threshold": {
                    "type": "outside",
                    "value_min": {"number": 20},
                    "value_max": {"number": 80},
                }
            },
            "50",
            False,
        ),
        (
            {
                "threshold": {
                    "type": "outside",
                    "value_min": {"number": 20},
                    "value_max": {"number": 80},
                }
            },
            "20",
            False,
        ),
        (
            {
                "threshold": {
                    "type": "outside",
                    "value_min": {"number": 20},
                    "value_max": {"number": 80},
                }
            },
            "80",
            False,
        ),
        (
            {
                "threshold": {
                    "type": "outside",
                    "value_min": {"number": 20},
                    "value_max": {"number": 80},
                }
            },
            "10",
            True,
        ),
        (
            {
                "threshold": {
                    "type": "outside",
                    "value_min": {"number": 20},
                    "value_max": {"number": 80},
                }
            },
            "90",
            True,
        ),
    ],
)
async def test_numerical_condition_thresholds(
    hass: HomeAssistant,
    condition_options: dict[str, Any],
    state_value: str,
    expected: bool,
) -> None:
    """Test numerical condition above/below thresholds."""
    test = await _setup_numerical_condition(
        hass,
        condition_options=condition_options,
        target_config={CONF_ENTITY_ID: ["test.entity_1"]},
    )

    hass.states.async_set("test.entity_1", state_value)
    assert test.async_check() is expected


@pytest.mark.parametrize(
    "state_value",
    ["cat", STATE_UNAVAILABLE, STATE_UNKNOWN],
)
async def test_numerical_condition_invalid_state(
    hass: HomeAssistant, state_value: str
) -> None:
    """Test numerical condition with non-numeric or unavailable state values."""
    test = await _setup_numerical_condition(
        hass,
        condition_options={"threshold": {"type": "above", "value": {"number": 50}}},
        target_config={CONF_ENTITY_ID: ["test.entity_1"]},
    )

    hass.states.async_set("test.entity_1", state_value)
    assert test.async_check() is False


async def test_numerical_condition_attribute_value_source(
    hass: HomeAssistant,
) -> None:
    """Test numerical condition reads from attribute when value_source is set."""
    test = await _setup_numerical_condition(
        hass,
        domain_specs={"test": DomainSpec(value_source="brightness")},
        condition_options={"threshold": {"type": "above", "value": {"number": 100}}},
        target_config={CONF_ENTITY_ID: ["test.entity_1"]},
    )

    # Attribute above threshold -> True
    hass.states.async_set("test.entity_1", "on", {"brightness": 200})
    assert test.async_check() is True

    # Attribute below threshold -> False
    hass.states.async_set("test.entity_1", "on", {"brightness": 50})
    assert test.async_check() is False

    # Missing attribute -> False
    hass.states.async_set("test.entity_1", "on", {})
    assert test.async_check() is False


async def test_numerical_condition_attribute_value_source_skips_unit_check(
    hass: HomeAssistant,
) -> None:
    """Test numerical condition with attribute value_source skips entity unit check.

    When value_source is set, the entity itself may not have ATTR_UNIT_OF_MEASUREMENT
    (e.g., climate target humidity). The valid_unit check should only apply to
    state-based entities, not attribute-based ones.
    """
    test = await _setup_numerical_condition(
        hass,
        domain_specs={"test": DomainSpec(value_source="humidity")},
        condition_options={"threshold": {"type": "above", "value": {"number": 50}}},
        target_config={CONF_ENTITY_ID: ["test.entity_1"]},
        valid_unit="%",
    )

    # Entity has no ATTR_UNIT_OF_MEASUREMENT but has the attribute value
    # The unit check should be skipped for attribute-based value sources
    hass.states.async_set("test.entity_1", "auto", {"humidity": 75})
    assert test.async_check() is True

    hass.states.async_set("test.entity_1", "auto", {"humidity": 25})
    assert test.async_check() is False


@pytest.mark.parametrize(
    ("valid_unit", "entity_unit", "expected"),
    [
        # valid_unit="%" — only matching unit passes
        ("%", "%", True),
        ("%", "°C", False),
        ("%", None, False),
        # valid_unit=None — only entities without unit pass
        (None, None, True),
        (None, "%", False),
        # valid_unit=UNDEFINED (default) — any unit passes
        (UNDEFINED, None, True),
        (UNDEFINED, "%", True),
        (UNDEFINED, "°C", True),
    ],
)
async def test_numerical_condition_valid_unit(
    hass: HomeAssistant,
    valid_unit: str | None | UndefinedType,
    entity_unit: str | None,
    expected: bool,
) -> None:
    """Test numerical condition valid_unit filtering."""
    test = await _setup_numerical_condition(
        hass,
        condition_options={"threshold": {"type": "above", "value": {"number": 50}}},
        target_config={CONF_ENTITY_ID: ["test.entity_1"]},
        valid_unit=valid_unit,
    )

    attrs = {ATTR_UNIT_OF_MEASUREMENT: entity_unit} if entity_unit else {}
    hass.states.async_set("test.entity_1", "75", attrs)
    assert test.async_check() is expected


@pytest.mark.parametrize(
    ("behavior", "one_match_expected"),
    [
        (BEHAVIOR_ANY, True),
        (BEHAVIOR_ALL, False),
    ],
)
async def test_numerical_condition_behavior(
    hass: HomeAssistant,
    behavior: str,
    one_match_expected: bool,
) -> None:
    """Test numerical condition with behavior any/all."""
    test = await _setup_numerical_condition(
        hass,
        condition_options={
            "threshold": {"type": "above", "value": {"number": 50}},
            ATTR_BEHAVIOR: behavior,
        },
        target_config={CONF_ENTITY_ID: ["test.entity_1", "test.entity_2"]},
    )

    # Both above -> True for any and all
    hass.states.async_set("test.entity_1", "75")
    hass.states.async_set("test.entity_2", "80")
    assert test.async_check() is True

    # Only one above -> depends on behavior
    hass.states.async_set("test.entity_2", "25")
    assert test.async_check() is one_match_expected

    # Neither above -> False for any and all
    hass.states.async_set("test.entity_1", "25")
    assert test.async_check() is False


async def test_numerical_condition_schema_requires_above_or_below(
    hass: HomeAssistant,
) -> None:
    """Test numerical condition schema requires at least above or below."""
    condition_cls = make_entity_numerical_condition({"test": DomainSpec()})

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": condition_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    config: dict[str, Any] = {
        CONF_CONDITION: "test",
        CONF_TARGET: {CONF_ENTITY_ID: "test.entity_1"},
        CONF_OPTIONS: {},
    }
    with pytest.raises(vol.Invalid):
        await async_validate_condition_config(hass, config)


@pytest.mark.parametrize(
    ("above", "below", "expected_result"),
    [
        (10.0, 10.0, does_not_raise()),
        (20.0, 10.0, pytest.raises(vol.Invalid, match="must not be greater")),
    ],
)
async def test_numerical_condition_schema_above_must_be_less_than_below(
    hass: HomeAssistant,
    above: float,
    below: float,
    expected_result: AbstractContextManager,
) -> None:
    """Test numerical condition schema rejects above >= below."""
    condition_cls = make_entity_numerical_condition({"test": DomainSpec()})

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": condition_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    config: dict[str, Any] = {
        CONF_CONDITION: "test",
        CONF_TARGET: {CONF_ENTITY_ID: "test.entity_1"},
        CONF_OPTIONS: {
            "threshold": {
                "type": "between",
                "value_min": {"number": above},
                "value_max": {"number": below},
            }
        },
    }
    with expected_result:
        await async_validate_condition_config(hass, config)


async def _setup_numerical_condition_with_unit(
    hass: HomeAssistant,
    condition_options: dict[str, Any],
    entity_ids: str | list[str],
    domain_specs: Mapping[str, DomainSpec] | None = None,
    base_unit: str = UnitOfTemperature.CELSIUS,
    unit_converter: type = TemperatureConverter,
) -> condition.ConditionChecker:
    """Set up a numerical condition with unit conversion via a mock platform."""
    condition_cls = make_entity_numerical_condition_with_unit(
        domain_specs or _DEFAULT_DOMAIN_SPECS, base_unit, unit_converter
    )

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": condition_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]

    config: dict[str, Any] = {
        CONF_CONDITION: "test",
        CONF_TARGET: {CONF_ENTITY_ID: entity_ids},
        CONF_OPTIONS: condition_options,
    }

    config = await async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert test is not None
    return test


@pytest.mark.parametrize(
    ("condition_options", "state_value", "expected"),
    [
        # above in °F, state in °C (base unit)
        # 75°F ≈ 23.89°C, so 25°C > 23.89°C → True
        (
            {
                "threshold": {
                    "type": "above",
                    "value": {"number": 75, "unit_of_measurement": "°F"},
                }
            },
            "25",
            True,
        ),
        # 75°F ≈ 23.89°C, so 20°C < 23.89°C → False
        (
            {
                "threshold": {
                    "type": "above",
                    "value": {"number": 75, "unit_of_measurement": "°F"},
                }
            },
            "20",
            False,
        ),
        # below in °F, state in °C
        # 70°F ≈ 21.11°C, so 20°C < 21.11°C → True
        (
            {
                "threshold": {
                    "type": "below",
                    "value": {"number": 70, "unit_of_measurement": "°F"},
                }
            },
            "20",
            True,
        ),
        # 70°F ≈ 21.11°C, so 25°C > 21.11°C → False
        (
            {
                "threshold": {
                    "type": "below",
                    "value": {"number": 70, "unit_of_measurement": "°F"},
                }
            },
            "25",
            False,
        ),
        # above in °C (same as base), state in °C
        (
            {
                "threshold": {
                    "type": "above",
                    "value": {"number": 20, "unit_of_measurement": "°C"},
                }
            },
            "25",
            True,
        ),
        (
            {
                "threshold": {
                    "type": "above",
                    "value": {"number": 20, "unit_of_measurement": "°C"},
                }
            },
            "15",
            False,
        ),
        # range with unit conversion
        # 60°F ≈ 15.56°C, 80°F ≈ 26.67°C
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 60, "unit_of_measurement": "°F"},
                    "value_max": {"number": 80, "unit_of_measurement": "°F"},
                }
            },
            "20",
            True,
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 60, "unit_of_measurement": "°F"},
                    "value_max": {"number": 80, "unit_of_measurement": "°F"},
                }
            },
            "10",
            False,
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 60, "unit_of_measurement": "°F"},
                    "value_max": {"number": 80, "unit_of_measurement": "°F"},
                }
            },
            "30",
            False,
        ),
    ],
)
async def test_numerical_condition_with_unit_thresholds(
    hass: HomeAssistant,
    condition_options: dict[str, Any],
    state_value: str,
    expected: bool,
) -> None:
    """Test numerical condition with unit conversion for numeric thresholds."""
    test = await _setup_numerical_condition_with_unit(
        hass,
        condition_options=condition_options,
        entity_ids="test.entity_1",
    )

    hass.states.async_set(
        "test.entity_1",
        state_value,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    assert test.async_check() is expected


async def test_numerical_condition_with_unit_entity_reference(
    hass: HomeAssistant,
) -> None:
    """Test numerical condition with unit conversion for entity reference limits."""
    test = await _setup_numerical_condition_with_unit(
        hass,
        condition_options={
            "threshold": {"type": "above", "value": {"entity": "sensor.temp_limit"}},
        },
        entity_ids="test.entity_1",
    )

    # Entity reference in °F → converted to °C for comparison
    # 75°F ≈ 23.89°C, 25°C > 23.89°C → True
    hass.states.async_set(
        "test.entity_1",
        "25",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "sensor.temp_limit",
        "75",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
    )
    assert test.async_check() is True

    # 75°F ≈ 23.89°C, 20°C < 23.89°C → False
    hass.states.async_set(
        "test.entity_1",
        "20",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    assert test.async_check() is False


async def test_numerical_condition_with_unit_entity_reference_incompatible_unit(
    hass: HomeAssistant,
) -> None:
    """Test numerical condition returns false with incompatible unit."""
    test = await _setup_numerical_condition_with_unit(
        hass,
        condition_options={
            "threshold": {"type": "above", "value": {"entity": "sensor.bad_limit"}},
        },
        entity_ids="test.entity_1",
    )

    hass.states.async_set(
        "test.entity_1",
        "25",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    # "%" is not a temperature unit → conversion fails → condition false
    hass.states.async_set(
        "sensor.bad_limit",
        "75",
        {ATTR_UNIT_OF_MEASUREMENT: "%"},
    )
    assert test.async_check() is False


async def test_numerical_condition_with_unit_tracked_value_conversion(
    hass: HomeAssistant,
) -> None:
    """Test that tracked entity values are converted from entity unit to base unit."""
    test = await _setup_numerical_condition_with_unit(
        hass,
        condition_options={
            "threshold": {
                "type": "above",
                "value": {"number": 20, "unit_of_measurement": "°C"},
            }
        },
        entity_ids="test.entity_1",
    )

    # Entity reports in °F: 80°F ≈ 26.67°C > 20°C → True
    hass.states.async_set(
        "test.entity_1",
        "80",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
    )
    assert test.async_check() is True

    # Entity reports in °F: 50°F ≈ 10°C < 20°C → False
    hass.states.async_set(
        "test.entity_1",
        "50",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
    )
    assert test.async_check() is False


async def test_numerical_condition_with_unit_attribute_value_source(
    hass: HomeAssistant,
) -> None:
    """Test numerical condition with unit conversion reads from attribute."""
    test = await _setup_numerical_condition_with_unit(
        hass,
        domain_specs={
            "test": DomainSpec(value_source="temperature"),
        },
        condition_options={
            "threshold": {
                "type": "above",
                "value": {"number": 75, "unit_of_measurement": "°F"},
            },
        },
        entity_ids="test.entity_1",
    )

    # 75°F ≈ 23.89°C, attribute=25°C > 23.89°C → True
    hass.states.async_set(
        "test.entity_1",
        "on",
        {
            "temperature": 25,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    assert test.async_check() is True

    # 75°F ≈ 23.89°C, attribute=20°C < 23.89°C → False
    hass.states.async_set(
        "test.entity_1",
        "on",
        {
            "temperature": 20,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    assert test.async_check() is False

    # Missing attribute → False
    hass.states.async_set("test.entity_1", "on", {})
    assert test.async_check() is False


async def test_numerical_condition_with_unit_get_entity_unit_override(
    hass: HomeAssistant,
) -> None:
    """Test that _get_entity_unit can be overridden for custom unit resolution."""

    class CustomCondition(EntityNumericalConditionWithUnitBase):
        """Condition that always reports entities as °F regardless of attributes."""

        _domain_specs = {"test": DomainSpec(value_source="temperature")}
        _base_unit = UnitOfTemperature.CELSIUS
        _unit_converter = TemperatureConverter

        def _get_entity_unit(self, entity_state: State) -> str | None:
            return UnitOfTemperature.FAHRENHEIT

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": CustomCondition}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    config: dict[str, Any] = {
        CONF_CONDITION: "test",
        CONF_TARGET: {CONF_ENTITY_ID: ["test.entity_1"]},
        CONF_OPTIONS: {
            "threshold": {
                "type": "above",
                "value": {"number": 20, "unit_of_measurement": "°C"},
            }
        },
    }
    config = await async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert test is not None

    # Entity attribute is 80 — _get_entity_unit returns °F,
    # so 80°F ≈ 26.67°C > 20°C → True
    hass.states.async_set("test.entity_1", "on", {"temperature": 80})
    assert test.async_check() is True

    # Entity attribute is 50 — 50°F ≈ 10°C < 20°C → False
    hass.states.async_set("test.entity_1", "on", {"temperature": 50})
    assert test.async_check() is False


async def test_numerical_condition_with_unit_schema_accepts_valid_units(
    hass: HomeAssistant,
) -> None:
    """Test that the schema accepts valid temperature units."""
    condition_cls = make_entity_numerical_condition_with_unit(
        {"test": DomainSpec()}, UnitOfTemperature.CELSIUS, TemperatureConverter
    )

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": condition_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    # Valid unit
    config: dict[str, Any] = {
        CONF_CONDITION: "test",
        CONF_TARGET: {CONF_ENTITY_ID: "test.entity_1"},
        CONF_OPTIONS: {
            "threshold": {
                "type": "above",
                "value": {"number": 20, "unit_of_measurement": "°F"},
            }
        },
    }
    result = await async_validate_condition_config(hass, config)
    assert result is not None


async def test_numerical_condition_with_unit_schema_rejects_invalid_units(
    hass: HomeAssistant,
) -> None:
    """Test that the schema rejects invalid temperature units."""
    condition_cls = make_entity_numerical_condition_with_unit(
        {"test": DomainSpec()}, UnitOfTemperature.CELSIUS, TemperatureConverter
    )

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": condition_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    # Invalid unit
    config: dict[str, Any] = {
        CONF_CONDITION: "test",
        CONF_TARGET: {CONF_ENTITY_ID: "test.entity_1"},
        CONF_OPTIONS: {
            "threshold": {
                "type": "above",
                "value": {"number": 20, "unit_of_measurement": "%"},
            }
        },
    }
    with pytest.raises(vol.Invalid):
        await async_validate_condition_config(hass, config)


@pytest.mark.parametrize(
    "state_value",
    ["cat", STATE_UNAVAILABLE, STATE_UNKNOWN],
)
async def test_numerical_condition_with_unit_invalid_state(
    hass: HomeAssistant, state_value: str
) -> None:
    """Test numerical condition with unit returns false for non-numeric state values."""
    test = await _setup_numerical_condition_with_unit(
        hass,
        condition_options={
            "threshold": {
                "type": "above",
                "value": {"number": 50, "unit_of_measurement": "°C"},
            },
        },
        entity_ids="test.entity_1",
    )

    hass.states.async_set(
        "test.entity_1",
        state_value,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    assert test.async_check() is False


async def test_numerical_condition_with_unit_missing_entity_reference(
    hass: HomeAssistant,
) -> None:
    """Test numerical condition returns false when entity reference does not exist."""
    test = await _setup_numerical_condition_with_unit(
        hass,
        condition_options={
            "threshold": {"type": "above", "value": {"entity": "sensor.nonexistent"}}
        },
        entity_ids="test.entity_1",
    )

    hass.states.async_set(
        "test.entity_1",
        "25",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    assert test.async_check() is False


@pytest.mark.parametrize(
    ("behavior", "one_match_expected"),
    [
        (BEHAVIOR_ANY, True),
        (BEHAVIOR_ALL, False),
    ],
)
async def test_numerical_condition_with_unit_behavior(
    hass: HomeAssistant,
    behavior: str,
    one_match_expected: bool,
) -> None:
    """Test numerical condition with unit conversion respects any/all behavior."""
    test = await _setup_numerical_condition_with_unit(
        hass,
        condition_options={
            ATTR_BEHAVIOR: behavior,
            "threshold": {
                "type": "above",
                "value": {"number": 50, "unit_of_measurement": "°C"},
            },
        },
        entity_ids=["test.entity_1", "test.entity_2"],
    )

    # Both above → True for any and all
    hass.states.async_set(
        "test.entity_1",
        "75",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "test.entity_2",
        "80",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    assert test.async_check() is True

    # Only one above → depends on behavior
    hass.states.async_set(
        "test.entity_2",
        "25",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    assert test.async_check() is one_match_expected

    # Neither above → False for any and all
    hass.states.async_set(
        "test.entity_1",
        "25",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    assert test.async_check() is False


async def _setup_state_condition(
    hass: HomeAssistant,
    states: str | bool | set[str | bool],
    target_config: dict[str, Any],
    condition_options: dict[str, Any] | None = None,
    domain_specs: Mapping[str, DomainSpec] | None = None,
    primary_entities_only: bool = True,
) -> condition.ConditionChecker:
    """Set up a state condition via a mock platform and return the checker."""
    condition_cls = make_entity_state_condition(
        domain_specs or _DEFAULT_DOMAIN_SPECS,
        states,
        primary_entities_only=primary_entities_only,
    )

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": condition_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    config: dict[str, Any] = {
        CONF_CONDITION: "test",
        CONF_TARGET: target_config,
        CONF_OPTIONS: condition_options or {},
    }

    config = await async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert test is not None
    return test


async def test_state_condition_single_entity(hass: HomeAssistant) -> None:
    """Test state condition with a single entity."""
    test = await _setup_state_condition(
        hass, target_config={CONF_ENTITY_ID: ["test.entity_1"]}, states=STATE_ON
    )

    hass.states.async_set("test.entity_1", STATE_ON)
    assert test.async_check() is True

    hass.states.async_set("test.entity_1", STATE_OFF)
    assert test.async_check() is False


async def test_state_condition_multiple_target_states(hass: HomeAssistant) -> None:
    """Test state condition matching any of multiple target states."""
    test = await _setup_state_condition(
        hass, target_config={CONF_ENTITY_ID: ["test.entity_1"]}, states={"on", "heat"}
    )

    hass.states.async_set("test.entity_1", "on")
    assert test.async_check() is True

    hass.states.async_set("test.entity_1", "heat")
    assert test.async_check() is True

    hass.states.async_set("test.entity_1", "off")
    assert test.async_check() is False


@pytest.mark.parametrize(
    "state_value",
    [STATE_UNAVAILABLE, STATE_UNKNOWN],
)
async def test_state_condition_unavailable_unknown(
    hass: HomeAssistant, state_value: str
) -> None:
    """Test state condition with unavailable/unknown entities.

    Uses three entities: entity_1 is on, entity_2 is unavailable/unknown,
    entity_3 varies. Unavailable/unknown entities are excluded from
    evaluation, so:
    - behavior any: passes if at least one *available* entity matches
    - behavior all: passes if all *available* entities match
    """
    # Single entity: unavailable/unknown → False
    test_single = await _setup_state_condition(
        hass, target_config={CONF_ENTITY_ID: ["test.entity_1"]}, states=STATE_ON
    )
    hass.states.async_set("test.entity_1", state_value)
    assert test_single.async_check() is False

    # behavior any: entity_1=on, entity_2=unavailable, entity_3=off
    # → True (entity_1 matches, entity_2 is skipped)
    test_any = await _setup_state_condition(
        hass,
        target_config={
            CONF_ENTITY_ID: ["test.entity_1", "test.entity_2", "test.entity_3"]
        },
        states=STATE_ON,
        condition_options={ATTR_BEHAVIOR: BEHAVIOR_ANY},
    )
    hass.states.async_set("test.entity_1", STATE_ON)
    hass.states.async_set("test.entity_2", state_value)
    hass.states.async_set("test.entity_3", STATE_OFF)
    assert test_any.async_check() is True

    # behavior any: entity_1=off, entity_2=unavailable, entity_3=off
    # → False (no available entity matches)
    hass.states.async_set("test.entity_1", STATE_OFF)
    assert test_any.async_check() is False

    # behavior all: entity_1=on, entity_2=unavailable, entity_3=on
    # → True (all *available* entities match, entity_2 is skipped)
    test_all = await _setup_state_condition(
        hass,
        target_config={
            CONF_ENTITY_ID: ["test.entity_1", "test.entity_2", "test.entity_3"]
        },
        states=STATE_ON,
        condition_options={ATTR_BEHAVIOR: BEHAVIOR_ALL},
    )
    hass.states.async_set("test.entity_1", STATE_ON)
    hass.states.async_set("test.entity_2", state_value)
    hass.states.async_set("test.entity_3", STATE_ON)
    assert test_all.async_check() is True

    # behavior all: entity_1=on, entity_2=unavailable, entity_3=off
    # → False (entity_3 is available and doesn't match)
    hass.states.async_set("test.entity_3", STATE_OFF)
    assert test_all.async_check() is False


async def test_state_condition_entity_not_found(hass: HomeAssistant) -> None:
    """Test state condition when entity does not exist."""
    test = await _setup_state_condition(
        hass, target_config={CONF_ENTITY_ID: ["test.nonexistent"]}, states=STATE_ON
    )

    # Entity doesn't exist — condition should be false
    assert test.async_check() is False


async def test_state_condition_attribute_value_source(hass: HomeAssistant) -> None:
    """Test state condition reads from attribute when value_source is set."""
    test = await _setup_state_condition(
        hass,
        target_config={CONF_ENTITY_ID: ["test.entity_1"]},
        states="heat",
        domain_specs={"test": DomainSpec(value_source="hvac_action")},
    )

    hass.states.async_set("test.entity_1", "on", {"hvac_action": "heat"})
    assert test.async_check() is True

    hass.states.async_set("test.entity_1", "on", {"hvac_action": "idle"})
    assert test.async_check() is False

    # Missing attribute
    hass.states.async_set("test.entity_1", "on", {})
    assert test.async_check() is False


@pytest.mark.parametrize(
    ("behavior", "one_match_expected"),
    [(BEHAVIOR_ANY, True), (BEHAVIOR_ALL, False)],
)
async def test_state_condition_behavior(
    hass: HomeAssistant, behavior: str, one_match_expected: bool
) -> None:
    """Test state condition with behavior any/all."""
    test = await _setup_state_condition(
        hass,
        target_config={CONF_ENTITY_ID: ["test.entity_1", "test.entity_2"]},
        states=STATE_ON,
        condition_options={ATTR_BEHAVIOR: behavior},
    )

    # Both on → True for any and all
    hass.states.async_set("test.entity_1", STATE_ON)
    hass.states.async_set("test.entity_2", STATE_ON)
    assert test.async_check() is True

    # Only one on → depends on behavior
    hass.states.async_set("test.entity_2", STATE_OFF)
    assert test.async_check() is one_match_expected

    # Neither on → False for any and all
    hass.states.async_set("test.entity_1", STATE_OFF)
    assert test.async_check() is False


async def test_state_condition_duration_not_met(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test state condition with duration: entity hasn't been in state long enough."""
    test = await _setup_state_condition(
        hass,
        target_config={CONF_ENTITY_ID: ["test.entity_1"]},
        states=STATE_ON,
        condition_options={CONF_FOR: {"seconds": 10}},
    )

    hass.states.async_set("test.entity_1", STATE_ON)
    await hass.async_block_till_done()

    # Just turned on — duration not met
    assert test.async_check() is False

    # Advance 5 seconds — still not enough
    freezer.tick(timedelta(seconds=5))
    assert test.async_check() is False


async def test_state_condition_duration_met(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test state condition with duration: entity has been in state long enough."""
    test = await _setup_state_condition(
        hass,
        target_config={CONF_ENTITY_ID: ["test.entity_1"]},
        states=STATE_ON,
        condition_options={CONF_FOR: {"seconds": 10}},
    )

    hass.states.async_set("test.entity_1", STATE_ON)
    await hass.async_block_till_done()

    # Advance past duration
    freezer.tick(timedelta(seconds=11))
    assert test.async_check() is True


async def test_state_condition_duration_zero_behaves_like_no_duration(
    hass: HomeAssistant,
) -> None:
    """Test that for: 0 behaves the same as omitting for.

    The UI defaults to 00:00:00, so a zero duration must not require the
    entity to have been in the state for any time — it should pass
    immediately, just like when for is not specified.
    """
    test = await _setup_state_condition(
        hass,
        target_config={CONF_ENTITY_ID: ["test.entity_1"]},
        states=STATE_ON,
        condition_options={CONF_FOR: {"seconds": 0}},
    )

    hass.states.async_set("test.entity_1", STATE_ON)
    await hass.async_block_till_done()

    # Should pass immediately — zero duration is the same as no duration
    assert test.async_check() is True


async def test_state_condition_duration_wrong_state(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test state condition with duration: entity in wrong state even after duration."""
    test = await _setup_state_condition(
        hass,
        target_config={CONF_ENTITY_ID: ["test.entity_1"]},
        states=STATE_ON,
        condition_options={CONF_FOR: {"seconds": 10}},
    )

    hass.states.async_set("test.entity_1", STATE_OFF)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=11))
    assert test.async_check() is False


async def test_state_condition_duration_reset_on_state_change(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test state condition with duration: timer resets when state changes."""
    test = await _setup_state_condition(
        hass,
        target_config={CONF_ENTITY_ID: ["test.entity_1"]},
        states=STATE_ON,
        condition_options={CONF_FOR: {"seconds": 10}},
    )

    hass.states.async_set("test.entity_1", STATE_ON)
    await hass.async_block_till_done()

    # Advance 8 seconds, then toggle off and back on — resets last_changed
    freezer.tick(timedelta(seconds=8))
    hass.states.async_set("test.entity_1", STATE_OFF)
    await hass.async_block_till_done()
    hass.states.async_set("test.entity_1", STATE_ON)
    await hass.async_block_till_done()

    # 5 seconds after retrigger — not enough
    freezer.tick(timedelta(seconds=5))
    assert test.async_check() is False

    # 6 more seconds (11 from retrigger) — now met
    freezer.tick(timedelta(seconds=6))
    assert test.async_check() is True


@pytest.mark.parametrize(
    ("behavior", "one_match_expected"),
    [(BEHAVIOR_ANY, True), (BEHAVIOR_ALL, False)],
)
async def test_state_condition_duration_behavior(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    behavior: str,
    one_match_expected: bool,
) -> None:
    """Test state condition with duration and behavior any/all."""
    test = await _setup_state_condition(
        hass,
        target_config={CONF_ENTITY_ID: ["test.entity_1", "test.entity_2"]},
        states=STATE_ON,
        condition_options={ATTR_BEHAVIOR: behavior, CONF_FOR: {"seconds": 10}},
    )

    hass.states.async_set("test.entity_1", STATE_ON)
    hass.states.async_set("test.entity_2", STATE_ON)
    await hass.async_block_till_done()

    # Both on but duration not met
    assert test.async_check() is False

    # Advance past duration — both on for long enough
    freezer.tick(timedelta(seconds=11))
    assert test.async_check() is True

    # Turn entity_2 off — only one on for duration → depends on behavior
    hass.states.async_set("test.entity_2", STATE_OFF)
    await hass.async_block_till_done()
    assert test.async_check() is one_match_expected

    # Neither on → False for any and all
    hass.states.async_set("test.entity_1", STATE_OFF)
    await hass.async_block_till_done()
    assert test.async_check() is False


@pytest.mark.parametrize(
    "state_value",
    [STATE_UNAVAILABLE, STATE_UNKNOWN],
)
async def test_state_condition_duration_unavailable_unknown(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, state_value: str
) -> None:
    """Test state condition with duration: unavailable/unknown entities are skipped.

    Uses three entities: entity_1=on, entity_2=unavailable, entity_3 varies.
    """
    # behavior any: entity_1=on (long enough), entity_2=unavailable, entity_3=off
    # → True (entity_1 matches and meets duration, entity_2 skipped)
    test_any = await _setup_state_condition(
        hass,
        target_config={
            CONF_ENTITY_ID: ["test.entity_1", "test.entity_2", "test.entity_3"]
        },
        states=STATE_ON,
        condition_options={ATTR_BEHAVIOR: BEHAVIOR_ANY, CONF_FOR: {"seconds": 10}},
    )
    hass.states.async_set("test.entity_1", STATE_ON)
    hass.states.async_set("test.entity_2", state_value)
    hass.states.async_set("test.entity_3", STATE_OFF)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=11))
    assert test_any.async_check() is True

    # behavior all: entity_1=on, entity_2=unavailable, entity_3=on (all long enough)
    # → True (all available entities match and meet duration)
    test_all = await _setup_state_condition(
        hass,
        target_config={
            CONF_ENTITY_ID: ["test.entity_1", "test.entity_2", "test.entity_3"]
        },
        states=STATE_ON,
        condition_options={ATTR_BEHAVIOR: BEHAVIOR_ALL, CONF_FOR: {"seconds": 10}},
    )
    hass.states.async_set("test.entity_1", STATE_ON)
    hass.states.async_set("test.entity_2", state_value)
    hass.states.async_set("test.entity_3", STATE_ON)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=11))
    assert test_all.async_check() is True

    # entity_3 off → not all available match
    hass.states.async_set("test.entity_3", STATE_OFF)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=11))
    assert test_all.async_check() is False


async def test_condition_checker_call_calls_async_check(
    hass: HomeAssistant,
) -> None:
    """Test that __call__ calls async_check."""

    class MockChecker(ConditionChecker):
        def _async_check(self, **kwargs: Any) -> bool:
            return True

    checker = MockChecker(hass)
    await checker.async_setup()
    check_mock = Mock(wraps=checker.async_check)
    checker.async_check = check_mock

    assert checker(hass) is True
    check_mock.assert_called_once()


async def test_condition_checker_del_calls_async_unload(
    hass: HomeAssistant,
) -> None:
    """Test that __del__ calls async_unload if not already called."""

    class MockChecker(ConditionChecker):
        def _async_check(self, **kwargs: Any) -> bool:
            return True

    checker = MockChecker(hass)
    unload_mock = Mock(wraps=checker.async_unload)
    checker.async_unload = unload_mock

    # Pylint says we should `del checker`. However, that's not guaranteed
    # to immediately call __del__.
    checker.__del__()  # pylint: disable=unnecessary-dunder-call
    unload_mock.assert_called_once()


async def test_condition_checker_del_skips_if_already_unloaded(
    hass: HomeAssistant,
) -> None:
    """Test that __del__ does not call async_unload if already called."""

    class MockChecker(ConditionChecker):
        def _async_check(self, **kwargs: Any) -> bool:
            return True

    checker = MockChecker(hass)
    unload_mock = Mock(wraps=checker.async_unload)
    checker.async_unload = unload_mock

    # First call sets the flag
    checker.async_unload()
    unload_mock.assert_called_once()
    unload_mock.reset_mock()

    # __del__ should skip since _unloaded is True
    # Pylint says we should `del checker`. However, that's not guaranteed
    # to immediately call __del__.
    checker.__del__()  # pylint: disable=unnecessary-dunder-call
    unload_mock.assert_not_called()


async def _setup_mock_integration(hass: HomeAssistant) -> None:
    """Set up a mock integration with conditions."""

    class MockCondition(Condition):
        def __new__(cls, *args: Any, **kwargs: Any) -> Condition:
            """Return a mock instance that tracks async_setup and async_unload calls."""
            mocked = Mock(spec=Condition)
            mocked.async_setup = AsyncMock()
            mocked.async_unload = Mock()
            return mocked

        @classmethod
        async def async_validate_config(
            cls, hass: HomeAssistant, config: ConfigType
        ) -> ConfigType:
            """Validate config."""
            return config  # Return the config unchanged for testing

        def _async_check(self, **kwargs: Any) -> bool | None:
            """Check the condition."""
            raise NotImplementedError

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": MockCondition}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )


@pytest.mark.parametrize(
    "compound_type",
    ["and", "or", "not"],
)
async def test_compound_condition_forwards_async_unload(
    hass: HomeAssistant, compound_type: str
) -> None:
    """Test that and/or/not compound conditions forward async_unload to children."""
    await _setup_mock_integration(hass)
    config = {
        "condition": compound_type,
        "conditions": [
            {"condition": "test"},
            {"condition": "test"},
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    # The compound checker should hold child checkers
    assert hasattr(test, "_conditions")
    assert len(test._conditions) == 2

    test.async_unload()

    for child in test._conditions:
        child.async_unload.assert_called_once()


@pytest.mark.parametrize(
    ("outer_type", "inner_type"),
    [
        (outer, inner)
        for outer in ("and", "or", "not")
        for inner in ("and", "or", "not")
    ],
)
async def test_nested_compound_condition_forwards_async_unload(
    hass: HomeAssistant, outer_type: str, inner_type: str
) -> None:
    """Test that nested compound conditions forward async_unload recursively."""
    await _setup_mock_integration(hass)
    config = {
        "condition": outer_type,
        "conditions": [
            {
                "condition": inner_type,
                "conditions": [{"condition": "test"}],
            },
            {"condition": "test"},
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    # Outer compound with 2 children: an inner compound and a leaf
    assert len(test._conditions) == 2
    inner_checker = test._conditions[0]
    assert hasattr(inner_checker, "_conditions")
    assert len(inner_checker._conditions) == 1

    test.async_unload()

    test._conditions[0]._conditions[0].async_unload.assert_called_once()
    test._conditions[1].async_unload.assert_called_once()


async def test_conditions_from_config_forwards_async_unload(
    hass: HomeAssistant,
) -> None:
    """Test that async_conditions_from_config forwards async_unload to children."""
    await _setup_mock_integration(hass)
    configs = [
        await condition.async_validate_condition_config(hass, {"condition": "test"}),
        await condition.async_validate_condition_config(hass, {"condition": "test"}),
    ]
    test = await condition.async_conditions_from_config(
        hass, configs, logging.getLogger(__name__), "test"
    )

    assert hasattr(test, "_conditions")
    assert len(test._conditions) == 2

    test.async_unload()

    for child in test._conditions:
        child.async_unload.assert_called_once()


@pytest.mark.parametrize(
    "inner_type",
    ["and", "or", "not"],
)
async def test_conditions_from_config_nested_forwards_async_unload(
    hass: HomeAssistant, inner_type: str
) -> None:
    """Test that async_conditions_from_config forwards async_unload recursively."""
    await _setup_mock_integration(hass)
    configs = [
        await condition.async_validate_condition_config(
            hass,
            {
                "condition": inner_type,
                "conditions": [{"condition": "test"}],
            },
        ),
        await condition.async_validate_condition_config(hass, {"condition": "test"}),
    ]
    test = await condition.async_conditions_from_config(
        hass, configs, logging.getLogger(__name__), "test"
    )

    assert len(test._conditions) == 2
    inner_checker = test._conditions[0]
    assert hasattr(inner_checker, "_conditions")
    assert len(inner_checker._conditions) == 1

    test.async_unload()

    test._conditions[0]._conditions[0].async_unload.assert_called_once()
    test._conditions[1].async_unload.assert_called_once()


_ATTR_DOMAIN_SPECS: Mapping[str, DomainSpec] = {
    "test": DomainSpec(value_source="test_attr")
}


async def _setup_attr_state_condition(
    hass: HomeAssistant,
    entity_ids: str | list[str],
    states: str | bool | set[str | bool],
    condition_options: dict[str, Any] | None = None,
) -> condition.ConditionChecker:
    """Set up an attribute-based state condition and return the checker."""
    condition_cls = make_entity_state_condition(
        _ATTR_DOMAIN_SPECS,
        states,
    )

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": condition_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]

    config: dict[str, Any] = {
        CONF_CONDITION: "test",
        CONF_TARGET: {CONF_ENTITY_ID: entity_ids},
        CONF_OPTIONS: condition_options or {},
    }

    config = await async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert test is not None
    return test


async def test_state_condition_attr_duration_not_met(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test attribute-based condition with duration: not met yet."""
    test = await _setup_attr_state_condition(
        hass,
        entity_ids="test.entity_1",
        states={True},
        condition_options={CONF_FOR: {"seconds": 10}},
    )

    hass.states.async_set("test.entity_1", STATE_ON, {"test_attr": True})
    await hass.async_block_till_done()

    # Just set — duration not met
    assert test.async_check() is False

    freezer.tick(timedelta(seconds=5))
    assert test.async_check() is False


async def test_state_condition_attr_duration_met(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test attribute-based condition with duration: met after waiting."""
    test = await _setup_attr_state_condition(
        hass,
        entity_ids="test.entity_1",
        states={True},
        condition_options={CONF_FOR: {"seconds": 10}},
    )

    hass.states.async_set("test.entity_1", STATE_ON, {"test_attr": True})
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=11))
    assert test.async_check() is True


async def test_state_condition_attr_duration_reset_on_attr_change(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test attribute-based condition: timer resets when attribute changes.

    This is the key difference from state-based duration: the tracked value
    is in an attribute, so state.last_changed does not capture it. The
    _valid_since tracking in async_setup handles this correctly.
    """
    test = await _setup_attr_state_condition(
        hass,
        entity_ids="test.entity_1",
        states={True},
        condition_options={CONF_FOR: {"seconds": 10}},
    )

    # Set attribute to True
    hass.states.async_set("test.entity_1", STATE_ON, {"test_attr": True})
    await hass.async_block_till_done()

    # After 8s, change attribute to False (state stays the same)
    freezer.tick(timedelta(seconds=8))
    hass.states.async_set("test.entity_1", STATE_ON, {"test_attr": False})
    await hass.async_block_till_done()

    # Set attribute back to True
    hass.states.async_set("test.entity_1", STATE_ON, {"test_attr": True})
    await hass.async_block_till_done()

    # 5s after re-set — not enough (timer was reset)
    freezer.tick(timedelta(seconds=5))
    assert test.async_check() is False

    # 6 more seconds (11 from re-set) — now met
    freezer.tick(timedelta(seconds=6))
    assert test.async_check() is True


@pytest.mark.parametrize(
    ("behavior", "one_match_expected"),
    [(BEHAVIOR_ANY, True), (BEHAVIOR_ALL, False)],
)
async def test_state_condition_attr_duration_behavior(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    behavior: str,
    one_match_expected: bool,
) -> None:
    """Test attribute-based condition with duration and behavior any/all."""
    test = await _setup_attr_state_condition(
        hass,
        entity_ids=["test.entity_1", "test.entity_2"],
        states={True},
        condition_options={ATTR_BEHAVIOR: behavior, CONF_FOR: {"seconds": 10}},
    )

    hass.states.async_set("test.entity_1", STATE_ON, {"test_attr": True})
    hass.states.async_set("test.entity_2", STATE_ON, {"test_attr": True})
    await hass.async_block_till_done()

    # Both matching but duration not met
    assert test.async_check() is False

    # Advance past duration — both matching long enough
    freezer.tick(timedelta(seconds=11))
    assert test.async_check() is True

    # Change entity_2 attribute — only one matching for duration
    hass.states.async_set("test.entity_2", STATE_ON, {"test_attr": False})
    await hass.async_block_till_done()
    assert test.async_check() is one_match_expected


@dataclass
class _AttrInitStep:
    """A state update step before the condition is created."""

    state: str
    attrs: dict[str, Any] = field(default_factory=dict)
    delay_before: int = 0


@pytest.mark.parametrize(
    ("steps", "duration", "initially_met"),
    [
        # Attribute set to valid 10s ago, no further changes → met (10 >= 5)
        (
            [_AttrInitStep(STATE_ON, {"test_attr": True})],
            10,
            True,
        ),
        # Attribute set to valid 3s ago → not met (3 < 5)
        (
            [_AttrInitStep(STATE_ON, {"test_attr": True})],
            3,
            False,
        ),
        # Attribute set to valid, then main state changes 2s later
        # (attribute stays valid). last_updated is bumped by the state change,
        # so the effective duration is only 2s from the second update → not met
        (
            [
                _AttrInitStep(STATE_ON, {"test_attr": True}),
                _AttrInitStep(STATE_OFF, {"test_attr": True}, delay_before=8),
            ],
            2,
            False,
        ),
        # Same as above but enough time after the state change → met
        (
            [
                _AttrInitStep(STATE_ON, {"test_attr": True}),
                _AttrInitStep(STATE_OFF, {"test_attr": True}, delay_before=2),
            ],
            8,
            True,
        ),
        # Attribute was invalid, then set to valid 4s ago → not met (4 < 5)
        (
            [
                _AttrInitStep(STATE_ON, {"test_attr": False}),
                _AttrInitStep(STATE_ON, {"test_attr": True}, delay_before=6),
            ],
            4,
            False,
        ),
        # Attribute was invalid, then set to valid 6s ago → met (6 >= 5)
        (
            [
                _AttrInitStep(STATE_ON, {"test_attr": False}),
                _AttrInitStep(STATE_ON, {"test_attr": True}, delay_before=4),
            ],
            6,
            True,
        ),
        # Attribute valid → invalid → valid 3s ago → not met (3 < 5)
        (
            [
                _AttrInitStep(STATE_ON, {"test_attr": True}),
                _AttrInitStep(STATE_ON, {"test_attr": False}, delay_before=5),
                _AttrInitStep(STATE_ON, {"test_attr": True}, delay_before=2),
            ],
            3,
            False,
        ),
    ],
    ids=[
        "valid_long_enough",
        "valid_too_short",
        "state_change_bumps_last_updated_not_met",
        "state_change_bumps_last_updated_met",
        "invalid_then_valid_not_met",
        "invalid_then_valid_met",
        "valid_invalid_valid_not_met",
    ],
)
async def test_state_condition_attr_duration_initial_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    steps: list[_AttrInitStep],
    duration: int,
    initially_met: bool,
) -> None:
    """Test attribute-based condition initialization without a recorder.

    With no recorder available the condition falls back to anchoring `for:`
    durations to the current state's last_updated. This is conservative: when
    the main state changes but the tracked attribute stays the same,
    last_updated is bumped and the effective duration resets (see the
    `state_change_bumps_last_updated_not_met` case). The recorder-backed
    variant in test_state_condition_attr_duration_initial_state_from_history
    refines this from real history.
    """
    for step in steps:
        freezer.tick(timedelta(seconds=step.delay_before))
        hass.states.async_set("test.entity_1", step.state, step.attrs)
        await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=duration))
    test = await _setup_attr_state_condition(
        hass,
        entity_ids="test.entity_1",
        states={True},
        condition_options={CONF_FOR: {"seconds": 5}},
    )

    assert test.async_check() is initially_met


async def _setup_attr_state_condition_with_target(
    hass: HomeAssistant,
    target: dict[str, Any],
    states: str | bool | set[str | bool],
    condition_options: dict[str, Any] | None = None,
) -> condition.ConditionChecker:
    """Set up an attribute-based state condition with a custom target."""
    condition_cls = make_entity_state_condition(
        _ATTR_DOMAIN_SPECS,
        states,
    )

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": condition_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    config: dict[str, Any] = {
        CONF_CONDITION: "test",
        CONF_TARGET: target,
        CONF_OPTIONS: condition_options or {},
    }

    config = await async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert test is not None
    return test


async def test_state_condition_attr_duration_entity_added_to_target(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that _valid_since is primed when an entity is added to the tracked set.

    When targeting by label, adding a label to an entity should make it
    tracked, and if it's already in a valid state, its duration should be
    primed from the state timestamps.
    """
    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Test Duration")

    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get_or_create(
        domain="test", platform="test", unique_id="duration_add"
    )

    # Entity starts valid but without the label
    hass.states.async_set(entry.entity_id, STATE_ON, {"test_attr": True})
    await hass.async_block_till_done()

    # Create condition targeting the label
    test = await _setup_attr_state_condition_with_target(
        hass,
        target={ATTR_LABEL_ID: label.label_id},
        states={True},
        condition_options={CONF_FOR: {"seconds": 5}},
    )

    # No entities have the label yet — condition has no entities to check,
    # behavior "any" with no matching entities returns False
    assert test.async_check() is False

    # Add the label to the entity — entity is already in valid state
    freezer.tick(timedelta(seconds=1))
    entity_reg.async_update_entity(entry.entity_id, labels={label.label_id})
    await hass.async_block_till_done()

    # Just added — duration not met yet
    assert test.async_check() is False

    # Wait past the duration from when entity was last_updated
    freezer.tick(timedelta(seconds=5))
    assert test.async_check() is True


async def test_state_condition_attr_duration_entity_removed_from_target(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test _valid_since is evicted when entity is removed from tracked set."""
    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Test Duration Remove")

    entity_reg = er.async_get(hass)
    entry1 = entity_reg.async_get_or_create(
        domain="test", platform="test", unique_id="duration_remove_1"
    )
    entry2 = entity_reg.async_get_or_create(
        domain="test", platform="test", unique_id="duration_remove_2"
    )
    # Both entities start with the label
    entity_reg.async_update_entity(entry1.entity_id, labels={label.label_id})
    entity_reg.async_update_entity(entry2.entity_id, labels={label.label_id})

    # Both entities in valid state
    hass.states.async_set(entry1.entity_id, STATE_ON, {"test_attr": True})
    hass.states.async_set(entry2.entity_id, STATE_ON, {"test_attr": True})
    await hass.async_block_till_done()

    test = await _setup_attr_state_condition_with_target(
        hass,
        target={ATTR_LABEL_ID: label.label_id},
        states={True},
        condition_options={
            ATTR_BEHAVIOR: BEHAVIOR_ALL,
            CONF_FOR: {"seconds": 5},
        },
    )

    # Wait past duration — both valid
    freezer.tick(timedelta(seconds=6))
    assert test.async_check() is True

    # Remove label from entry2
    entity_reg.async_update_entity(entry2.entity_id, labels=set())
    await hass.async_block_till_done()

    # Condition should still be True — only entry1 is tracked now, and it's valid
    assert test.async_check() is True

    # Now remove label from entry1 too
    entity_reg.async_update_entity(entry1.entity_id, labels=set())
    await hass.async_block_till_done()

    # No entities tracked — "all" with empty set is vacuously True
    assert test.async_check() is True

    # Change entry1 to invalid state and re-add its label
    hass.states.async_set(entry1.entity_id, STATE_ON, {"test_attr": False})
    await hass.async_block_till_done()
    entity_reg.async_update_entity(entry1.entity_id, labels={label.label_id})
    await hass.async_block_till_done()

    # entry1 is now tracked again but invalid — "all" fails
    freezer.tick(timedelta(seconds=10))
    assert test.async_check() is False


async def test_state_condition_attr_duration_entity_added_then_state_changes(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that a newly added entity's state changes are properly tracked."""
    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Test Duration Track")

    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get_or_create(
        domain="test", platform="test", unique_id="duration_track"
    )

    # Entity starts in invalid state
    hass.states.async_set(entry.entity_id, STATE_ON, {"test_attr": False})
    await hass.async_block_till_done()

    # Create condition targeting the label
    test = await _setup_attr_state_condition_with_target(
        hass,
        target={ATTR_LABEL_ID: label.label_id},
        states={True},
        condition_options={CONF_FOR: {"seconds": 5}},
    )

    # Add the label — entity is invalid, so no priming
    entity_reg.async_update_entity(entry.entity_id, labels={label.label_id})
    await hass.async_block_till_done()
    assert test.async_check() is False

    # Now change to valid state
    freezer.tick(timedelta(seconds=1))
    hass.states.async_set(entry.entity_id, STATE_ON, {"test_attr": True})
    await hass.async_block_till_done()

    # Just became valid — not long enough
    freezer.tick(timedelta(seconds=3))
    assert test.async_check() is False

    # Now past the duration
    freezer.tick(timedelta(seconds=3))
    assert test.async_check() is True


async def test_state_condition_attr_duration_unrelated_attr_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that unrelated attribute updates don't reset the duration timer.

    When the tracked attribute stays valid but another attribute changes,
    _update_valid_since must not overwrite the existing timestamp.
    """
    test = await _setup_attr_state_condition(
        hass,
        entity_ids="test.entity_1",
        states={True},
        condition_options={CONF_FOR: {"seconds": 10}},
    )

    # Set tracked attribute to True
    hass.states.async_set("test.entity_1", STATE_ON, {"test_attr": True, "other": "a"})
    await hass.async_block_till_done()

    # After 6s, change an unrelated attribute (tracked attr stays True)
    freezer.tick(timedelta(seconds=6))
    hass.states.async_set("test.entity_1", STATE_ON, {"test_attr": True, "other": "b"})
    await hass.async_block_till_done()

    # After 5 more seconds (11 total from initial set), the duration
    # should be met — the unrelated attribute change must NOT have
    # reset the timer.
    freezer.tick(timedelta(seconds=5))
    assert test.async_check() is True


async def _record_attr_steps(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    start: datetime,
    entity_id: str,
    steps: list[_AttrInitStep],
) -> int:
    """Record a series of state writes into the recorder at controlled times.

    Returns the number of seconds elapsed from `start` to the final write.
    """
    elapsed = 0
    for step in steps:
        elapsed += step.delay_before
        freezer.move_to(start + timedelta(seconds=elapsed))
        hass.states.async_set(entity_id, step.state, step.attrs)
        await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    return elapsed


@pytest.mark.parametrize(
    ("steps", "wait_before_setup", "initially_met"),
    [
        # Valid the entire time → met (10s >= 5s).
        ([_AttrInitStep(STATE_ON, {"test_attr": True})], 10, True),
        # Valid for less than the `for:` window → not met (3s < 5s).
        ([_AttrInitStep(STATE_ON, {"test_attr": True})], 3, False),
        # The tracked attribute stayed valid across an unrelated main-state
        # change. The OFF write bumps last_updated, but history shows the
        # attribute never left the valid range → met. This is exactly the case
        # the conservative last_updated anchor reports wrong (it returns False;
        # see test_state_condition_attr_duration_initial_state).
        (
            [
                _AttrInitStep(STATE_ON, {"test_attr": True}),
                _AttrInitStep(STATE_OFF, {"test_attr": True}, delay_before=8),
            ],
            2,
            True,
        ),
        # Invalid, then valid 6s before setup → met (6s >= 5s).
        (
            [
                _AttrInitStep(STATE_ON, {"test_attr": False}),
                _AttrInitStep(STATE_ON, {"test_attr": True}, delay_before=4),
            ],
            6,
            True,
        ),
        # Invalid, then valid only 4s before setup → not met (4s < 5s).
        (
            [
                _AttrInitStep(STATE_ON, {"test_attr": False}),
                _AttrInitStep(STATE_ON, {"test_attr": True}, delay_before=6),
            ],
            4,
            False,
        ),
    ],
    ids=[
        "valid_long_enough",
        "valid_too_short",
        "valid_across_state_change",
        "invalid_then_valid_met",
        "invalid_then_valid_not_met",
    ],
)
async def test_state_condition_attr_duration_initial_state_from_history(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    steps: list[_AttrInitStep],
    wait_before_setup: int,
    initially_met: bool,
) -> None:
    """Test attribute-based `for:` priming from recorder history.

    With the recorder available, the condition walks recent history to find
    when the tracked value actually entered its current continuous valid run,
    rather than conservatively anchoring to the current state's last_updated.
    The `valid_across_state_change` case is the key improvement: an unrelated
    main-state change no longer resets the duration.
    """
    entity_id = "test.entity_1"
    start = dt_util.utcnow()
    with freeze_time(start) as freezer:
        elapsed = await _record_attr_steps(hass, freezer, start, entity_id, steps)

        freezer.move_to(start + timedelta(seconds=elapsed + wait_before_setup))
        test = await _setup_attr_state_condition(
            hass,
            entity_ids=entity_id,
            states={True},
            condition_options={CONF_FOR: {"seconds": 5}},
        )
        assert test.async_check() is initially_met


async def test_state_condition_attr_duration_history_includes_attr_only_changes(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Attribute-only invalidations inside the window must reset the timer.

    The tracked value dips invalid and recovers through attribute-only changes
    (the main state stays ON throughout). Those rows are only returned when the
    history query passes significant_changes_only=False; were they dropped, the
    window would look continuously valid and the condition would wrongly report
    the `for:` duration as met.
    """
    entity_id = "test.entity_1"
    start = dt_util.utcnow()
    steps = [
        _AttrInitStep(STATE_ON, {"test_attr": True}),
        _AttrInitStep(STATE_ON, {"test_attr": False}, delay_before=6),
        _AttrInitStep(STATE_ON, {"test_attr": True}, delay_before=2),
    ]
    with freeze_time(start) as freezer:
        elapsed = await _record_attr_steps(hass, freezer, start, entity_id, steps)

        freezer.move_to(start + timedelta(seconds=elapsed + 2))
        test = await _setup_attr_state_condition(
            hass,
            entity_ids=entity_id,
            states={True},
            condition_options={CONF_FOR: {"seconds": 5}},
        )
        # Valid only for the last 2s (since the recovery at t=8); the dip to
        # invalid at t=6 falls inside the 5s window → not met.
        assert test.async_check() is False


@pytest.mark.parametrize(
    ("behavior", "expected"),
    [(BEHAVIOR_ANY, True), (BEHAVIOR_ALL, False)],
)
async def test_state_condition_attr_duration_from_history_multiple_entities(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    behavior: str,
    expected: bool,
) -> None:
    """History priming covers every targeted entity in a single query.

    entity_1 has been valid long enough; entity_2 only recently became valid,
    so `any` passes while `all` does not.
    """
    start = dt_util.utcnow()
    with freeze_time(start) as freezer:
        hass.states.async_set("test.entity_1", STATE_ON, {"test_attr": True})
        hass.states.async_set("test.entity_2", STATE_ON, {"test_attr": False})
        await hass.async_block_till_done()

        freezer.move_to(start + timedelta(seconds=7))
        hass.states.async_set("test.entity_2", STATE_ON, {"test_attr": True})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        freezer.move_to(start + timedelta(seconds=10))
        test = await _setup_attr_state_condition(
            hass,
            entity_ids=["test.entity_1", "test.entity_2"],
            states={True},
            condition_options={ATTR_BEHAVIOR: behavior, CONF_FOR: {"seconds": 5}},
        )
        # entity_1 valid for 10s (met); entity_2 valid for only 3s (not met).
        assert test.async_check() is expected


@pytest.mark.parametrize(
    "history_error",
    [SQLAlchemyError("boom"), TimeoutError()],
    ids=["db_error", "timeout"],
)
async def test_state_condition_attr_duration_history_error_falls_back(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    history_error: Exception,
) -> None:
    """A failing/slow history query must not break setup; it falls back.

    The tracked attribute stayed valid across an unrelated main-state change,
    so a successful history read would report the duration as met. When the
    query errors or times out, the condition keeps the conservative
    last_updated anchor (set when the tracker was wired up) instead, which here
    reports not met — and crucially, setup does not raise.
    """
    entity_id = "test.entity_1"
    start = dt_util.utcnow()
    with freeze_time(start) as freezer:
        hass.states.async_set(entity_id, STATE_ON, {"test_attr": True})
        await hass.async_block_till_done()
        freezer.move_to(start + timedelta(seconds=8))
        hass.states.async_set(entity_id, STATE_OFF, {"test_attr": True})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        freezer.move_to(start + timedelta(seconds=10))
        with patch(
            "homeassistant.components.recorder.history.get_significant_states",
            side_effect=history_error,
        ):
            test = await _setup_attr_state_condition(
                hass,
                entity_ids=entity_id,
                states={True},
                condition_options={CONF_FOR: {"seconds": 5}},
            )

        # Fell back to the conservative anchor (last_updated bumped at t=8),
        # so the 5s `for:` is not satisfied 2s later.
        assert test.async_check() is False


async def test_state_condition_attr_duration_history_lookback_capped(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """The history lookback is capped, regardless of a longer `for:` duration."""
    entity_id = "test.entity_1"
    start = dt_util.utcnow()
    with freeze_time(start):
        hass.states.async_set(entity_id, STATE_ON, {"test_attr": True})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        captured: dict[str, datetime] = {}

        def _capture(hass_: HomeAssistant, start_time: datetime, **kwargs: Any) -> dict:
            captured["start_time"] = start_time
            return {}

        with patch(
            "homeassistant.components.recorder.history.get_significant_states",
            side_effect=_capture,
        ):
            await _setup_attr_state_condition(
                hass,
                entity_ids=entity_id,
                states={True},
                condition_options={CONF_FOR: {"hours": 8}},
            )

        # The 8h `for:` is clamped to the 6h cap.
        assert dt_util.utcnow() - captured["start_time"] == MAX_HISTORY_PRIMING_LOOKBACK


async def test_state_condition_attr_duration_history_long_for_uses_live_anchor(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """A `for:` longer than the lookback cap still uses the live anchor.

    The entity has been valid for 10h (longer than the 6h history cap). History
    alone can only prove the last 6h, but the live state's last_updated (10h
    ago, never changed) proves the full run, so the 8h `for:` is met. This
    requires combining history with the live anchor rather than overriding it.
    """
    entity_id = "test.entity_1"
    start = dt_util.utcnow()
    with freeze_time(start) as freezer:
        hass.states.async_set(entity_id, STATE_ON, {"test_attr": True})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        freezer.move_to(start + timedelta(hours=10))
        test = await _setup_attr_state_condition(
            hass,
            entity_ids=entity_id,
            states={True},
            condition_options={CONF_FOR: {"hours": 8}},
        )
        assert test.async_check() is True


async def test_state_condition_attr_duration_history_loaded_for_added_entity(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """History is loaded for an entity added to the target after setup.

    The entity is only tracked once it gains the targeted label. Resolving its
    anchor runs in a background task, and the entity is not counted until that
    completes (no interim conservative anchor). Once loaded, its anchor comes
    from history just like the initial set: the attribute stayed valid across an
    unrelated main-state change, so the duration is met even though the live
    last_updated anchor alone (bumped by the OFF write) would report not met.
    """
    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Test Late History")
    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get_or_create(
        domain="test", platform="test", unique_id="late_history"
    )
    entity_id = entry.entity_id

    start = dt_util.utcnow()
    with freeze_time(start) as freezer:
        # Valid since t=0; unrelated main-state change at t=8 keeps the attr valid.
        hass.states.async_set(entity_id, STATE_ON, {"test_attr": True})
        await hass.async_block_till_done()
        freezer.move_to(start + timedelta(seconds=8))
        hass.states.async_set(entity_id, STATE_OFF, {"test_attr": True})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        # The entity has no label yet, so it is not tracked at setup.
        freezer.move_to(start + timedelta(seconds=10))
        test = await _setup_attr_state_condition_with_target(
            hass,
            target={ATTR_LABEL_ID: label.label_id},
            states={True},
            condition_options={CONF_FOR: {"seconds": 5}},
        )
        assert test.async_check() is False

        # Adding the label tracks the entity, but its anchor is resolved in a
        # background task. Until that completes the entity has no _valid_since
        # entry and is not counted yet — even though it will be met once loaded.
        # Hold the recorder flush open so the load deterministically cannot
        # finish before the intermediate check.
        instance = get_instance(hass)
        gate: asyncio.Future[None] = hass.loop.create_future()
        with patch.object(instance, "async_get_commit_future", return_value=gate):
            entity_reg.async_update_entity(entity_id, labels={label.label_id})
            assert test.async_check() is False

            # Release the flush; the query runs and the anchor is stored.
            gate.set_result(None)
            await hass.async_block_till_done(wait_background_tasks=True)

        # History loaded: continuously valid for 10s → 5s `for:` is met.
        assert test.async_check() is True


async def test_state_condition_attr_duration_not_counted_while_history_loads(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """The known gap: a new entity is not counted while its history loads.

    Resolving a newly tracked entity's `for:` anchor is asynchronous. Until the
    recorder read completes the entity has no `_valid_since` entry, so the
    condition does not count it — even though it will be met once loaded. This
    holds the recorder read open to observe that window deterministically.
    """
    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Loading Gap")
    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get_or_create(
        domain="test", platform="test", unique_id="loading_gap"
    )
    entity_id = entry.entity_id

    start = dt_util.utcnow()
    with freeze_time(start) as freezer:
        hass.states.async_set(entity_id, STATE_ON, {"test_attr": True})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        # Valid for 10s by the time it is added, so once loaded the 5s `for:`
        # is met.
        freezer.move_to(start + timedelta(seconds=10))
        test = await _setup_attr_state_condition_with_target(
            hass,
            target={ATTR_LABEL_ID: label.label_id},
            states={True},
            condition_options={CONF_FOR: {"seconds": 5}},
        )
        assert test.async_check() is False

        # Hold the recorder flush open so the background history load can't
        # finish, then add the entity to the target.
        instance = get_instance(hass)
        gate: asyncio.Future[None] = hass.loop.create_future()
        with patch.object(instance, "async_get_commit_future", return_value=gate):
            entity_reg.async_update_entity(entity_id, labels={label.label_id})
            # Let the prime task start and block on the held flush.
            await asyncio.sleep(0)
            # Load in flight → no anchor yet → entity not counted.
            assert test.async_check() is False

            # Release the flush; the query runs and the anchor is stored.
            gate.set_result(None)
            await hass.async_block_till_done(wait_background_tasks=True)

        # Loaded now → met.
        assert test.async_check() is True


async def test_state_condition_attr_duration_benign_change_during_load_keeps_history(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """A valid live change during the load does not discard history.

    If the entity stays valid while its history loads, the run is unbroken and
    history's earlier run-start is still accurate, so it is applied. An unrelated
    attribute write must not reset the anchor to "now".
    """
    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Benign During Load")
    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get_or_create(
        domain="test", platform="test", unique_id="benign_during_load"
    )
    entity_id = entry.entity_id

    start = dt_util.utcnow()
    with freeze_time(start) as freezer:
        # Valid since t=0; history anchors here, well past the 5s `for:`.
        hass.states.async_set(entity_id, STATE_ON, {"test_attr": True})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        freezer.move_to(start + timedelta(seconds=10))
        test = await _setup_attr_state_condition_with_target(
            hass,
            target={ATTR_LABEL_ID: label.label_id},
            states={True},
            condition_options={CONF_FOR: {"seconds": 5}},
        )

        instance = get_instance(hass)
        gate: asyncio.Future[None] = hass.loop.create_future()
        with patch.object(instance, "async_get_commit_future", return_value=gate):
            entity_reg.async_update_entity(entity_id, labels={label.label_id})
            await asyncio.sleep(0)  # prime task blocks on the held flush

            # Unrelated attribute write while loading: still valid (run unbroken).
            hass.states.async_set(
                entity_id, STATE_ON, {"test_attr": True, "other": "x"}
            )
            await asyncio.sleep(0)

            # Advance so the change-time anchor alone would satisfy the 5s `for:`.
            # The entity must still not be counted while its history is loading —
            # the live listener leaves primed entities alone, so there is no
            # interim anchor for the change to set.
            freezer.move_to(start + timedelta(seconds=18))
            assert test.async_check() is False

            gate.set_result(None)
            await hass.async_block_till_done(wait_background_tasks=True)

        # History was applied despite the benign change → valid since t=0 → met.
        assert test.async_check() is True


async def test_state_condition_attr_duration_invalidation_during_load_discards_history(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """An invalidation during the load discards the (now stale) history.

    The commit flush only guarantees history up to the flush point; a dip that
    commits after it is invisible to the query, so history would still show the
    old continuous run. The live listener saw the break, so on revalidation the
    anchor comes from live tracking (the post-dip time), not history.
    """
    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Dip During Load")
    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get_or_create(
        domain="test", platform="test", unique_id="dip_during_load"
    )
    entity_id = entry.entity_id

    start = dt_util.utcnow()
    with freeze_time(start) as freezer:
        # Valid since t=0; history alone would (stalely) anchor here and report
        # the 5s `for:` as met.
        hass.states.async_set(entity_id, STATE_ON, {"test_attr": True})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        freezer.move_to(start + timedelta(seconds=10))
        test = await _setup_attr_state_condition_with_target(
            hass,
            target={ATTR_LABEL_ID: label.label_id},
            states={True},
            condition_options={CONF_FOR: {"seconds": 5}},
        )

        instance = get_instance(hass)
        gate: asyncio.Future[None] = hass.loop.create_future()
        with patch.object(instance, "async_get_commit_future", return_value=gate):
            entity_reg.async_update_entity(entity_id, labels={label.label_id})
            await asyncio.sleep(0)  # prime task blocks on the held flush

            # Dip invalid then valid again while loading: the run broke.
            hass.states.async_set(entity_id, STATE_ON, {"test_attr": False})
            await asyncio.sleep(0)
            hass.states.async_set(entity_id, STATE_ON, {"test_attr": True})
            await asyncio.sleep(0)

            gate.set_result(None)
            await hass.async_block_till_done(wait_background_tasks=True)

        # Stale history was discarded; the anchor is the post-dip time (now), so
        # the 5s `for:` is not yet met.
        assert test.async_check() is False


async def test_state_condition_attr_duration_history_flushes_before_query(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Pending recorder writes are flushed before the history query.

    `get_significant_states` only sees committed rows. A state change that
    already happened but is still queued in the recorder would be missed by
    both the query and the live listener (which only sees changes after it
    subscribes), so the queue must be flushed before querying.
    """
    entity_id = "test.entity_1"
    hass.states.async_set(entity_id, STATE_ON, {"test_attr": True})
    await hass.async_block_till_done()

    call_order: list[str] = []
    instance = get_instance(hass)
    real_commit_future = instance.async_get_commit_future
    real_query = history.get_significant_states

    def _spy_commit_future() -> Any:
        call_order.append("flush")
        return real_commit_future()

    def _spy_query(*args: Any, **kwargs: Any) -> Any:
        call_order.append("query")
        return real_query(*args, **kwargs)

    with (
        patch.object(instance, "async_get_commit_future", _spy_commit_future),
        patch(
            "homeassistant.components.recorder.history.get_significant_states",
            _spy_query,
        ),
    ):
        await _setup_attr_state_condition(
            hass,
            entity_ids=entity_id,
            states={True},
            condition_options={CONF_FOR: {"seconds": 5}},
        )

    assert call_order == ["flush", "query"]


async def test_async_setup_creates_history_priming_manager(
    hass: HomeAssistant,
) -> None:
    """The priming manager is created during condition setup, not on demand."""
    # condition.async_setup runs as part of the test hass fixture.
    assert isinstance(hass.data[_DATA_HISTORY_PRIMING_MANAGER], _HistoryPrimingManager)


async def test_history_priming_manager_serializes_queries(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Queries run one at a time even when many conditions prime together."""
    manager = _HistoryPrimingManager(hass)
    instance = get_instance(hass)

    running = 0
    max_running = 0
    release = asyncio.Event()
    started = asyncio.Event()

    async def _job(_recorder: Recorder) -> str:
        nonlocal running, max_running
        running += 1
        max_running = max(max_running, running)
        started.set()
        await release.wait()
        running -= 1
        return "ok"

    # No pending commit, so flushing is instant and only query serialization
    # is exercised.
    with patch.object(instance, "async_get_commit_future", return_value=None):
        tasks = [asyncio.create_task(manager.async_prime(_job)) for _ in range(5)]
        # The first job holds the query lock; the rest must queue behind it.
        await started.wait()
        await asyncio.sleep(0)
        assert running == 1
        release.set()
        results = await asyncio.gather(*tasks)

    assert results == ["ok"] * 5
    assert max_running == 1


async def _advance_until(predicate: Callable[[], bool]) -> None:
    """Pump the event loop until predicate holds, failing if it never does.

    Avoids coupling tests to an exact number of internal await hops while still
    failing cleanly rather than hanging on a regression.
    """
    for _ in range(1000):
        if predicate():
            return
        await asyncio.sleep(0)
    pytest.fail("condition was not reached")


async def test_history_priming_manager_does_not_ride_in_flight_flush(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """A priming never rides a flush that began before it arrived (the lobby).

    The flush commits changes still queued in the recorder so the history read
    sees them. A condition that started tracking after an in-flight flush began
    could miss its own just-queued change if it rode that flush, so it waits the
    flush out and a fresh one is performed for it. Without the lobby step this
    test fails: the late arrivals would ride the first flush (it would stay at
    one flush total) instead of sharing a second, fresh one.
    """
    manager = _HistoryPrimingManager(hass)
    instance = get_instance(hass)

    flush_futures: list[asyncio.Future[None]] = []

    def _spy_commit_future() -> asyncio.Future[None]:
        fut = hass.loop.create_future()
        flush_futures.append(fut)
        return fut

    async def _job(_recorder: Recorder) -> str:
        return "done"

    with patch.object(instance, "async_get_commit_future", _spy_commit_future):
        # C0 claims the flush and is mid-flush (its commit future is pending).
        c0 = asyncio.create_task(manager.async_prime(_job))
        await _advance_until(lambda: len(flush_futures) == 1)

        # Two conditions arrive while C0's flush runs; they must not ride it.
        c1 = asyncio.create_task(manager.async_prime(_job))
        c2 = asyncio.create_task(manager.async_prime(_job))

        # C0's flush completes; C1 then performs a fresh flush and C2 rides it.
        flush_futures[0].set_result(None)
        assert await c0 == "done"
        await _advance_until(lambda: len(flush_futures) == 2)

        flush_futures[1].set_result(None)
        assert await asyncio.gather(c1, c2) == ["done", "done"]
        # One fresh flush shared by C1 and C2, not one each (and not C0's stale
        # one): C1 flushed, C2 rode it.
        assert len(flush_futures) == 2


async def test_history_priming_manager_retries_after_cancelled_flush(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """A rider re-flushes when the flush it rode was cancelled before completing.

    If the condition performing a generation's shared flush is cancelled by its
    timeout while awaiting the commit, the riders must not read against the
    unflushed queue — they perform a fresh flush instead. Without that retry this
    test fails: the rider would proceed on the cancelled flush and never make a
    second one.
    """
    manager = _HistoryPrimingManager(hass)
    instance = get_instance(hass)

    flush_futures: list[asyncio.Future[None]] = []

    def _spy_commit_future() -> asyncio.Future[None]:
        fut = hass.loop.create_future()
        flush_futures.append(fut)
        return fut

    async def _job(_recorder: Recorder) -> str:
        return "done"

    with patch.object(instance, "async_get_commit_future", _spy_commit_future):
        # C0 takes the lobby so c1 and c2 form one generation behind it.
        c0 = asyncio.create_task(manager.async_prime(_job))
        await _advance_until(lambda: len(flush_futures) == 1)
        c1 = asyncio.create_task(manager.async_prime(_job))
        c2 = asyncio.create_task(manager.async_prime(_job))
        flush_futures[0].set_result(None)
        assert await c0 == "done"

        # c1 performs the generation's flush (the second one) and c2 rides it.
        await _advance_until(lambda: len(flush_futures) == 2)

        # c1 is cancelled mid-flush, as its timeout would do. c2 must then run
        # its own fresh flush rather than ride c1's cancelled one.
        c1.cancel()
        with pytest.raises(asyncio.CancelledError):
            await c1
        await _advance_until(lambda: len(flush_futures) == 3)

        flush_futures[2].set_result(None)
        assert await c2 == "done"


async def test_history_priming_manager_cancelled_lobby_waiter(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """A priming cancelled while waiting in the lobby doesn't wedge later ones.

    A condition whose timeout fires while it waits for an in-flight flush is
    cancelled. That must leave the manager able to flush for the next priming.
    """
    manager = _HistoryPrimingManager(hass)
    instance = get_instance(hass)

    flush_futures: list[asyncio.Future[None]] = []

    def _spy_commit_future() -> asyncio.Future[None]:
        fut = hass.loop.create_future()
        flush_futures.append(fut)
        return fut

    async def _job(_recorder: Recorder) -> str:
        return "done"

    with patch.object(instance, "async_get_commit_future", _spy_commit_future):
        c0 = asyncio.create_task(manager.async_prime(_job))
        await _advance_until(lambda: len(flush_futures) == 1)
        # A second priming parks in the lobby (reached in one step, as its lock
        # acquire is uncontended), then its timeout cancels it.
        waiter = asyncio.create_task(manager.async_prime(_job))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter

        # C0 finishes; a later priming still flushes and completes normally.
        flush_futures[0].set_result(None)
        assert await c0 == "done"
        later = asyncio.create_task(manager.async_prime(_job))
        await _advance_until(lambda: len(flush_futures) == 2)
        flush_futures[1].set_result(None)
        assert await later == "done"


async def test_state_condition_multi_state_duration_uses_history(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """A multi-state condition reads history to anchor across in-set toggles.

    A transition within the valid set (here ON->OFF) bumps `last_changed` even
    though the condition stays valid, so `last_changed` alone is too
    conservative; history finds the true start of the run.
    """
    entity_id = "test.entity_1"
    start = dt_util.utcnow()
    with freeze_time(start) as freezer:
        hass.states.async_set(entity_id, STATE_ON)
        await hass.async_block_till_done()
        # Toggle within the valid set: still valid, but last_changed jumps to t=8.
        freezer.move_to(start + timedelta(seconds=8))
        hass.states.async_set(entity_id, STATE_OFF)
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        freezer.move_to(start + timedelta(seconds=10))
        test = await _setup_state_condition(
            hass,
            states={STATE_ON, STATE_OFF},
            target_config={CONF_ENTITY_ID: [entity_id]},
            condition_options={CONF_FOR: {"seconds": 5}},
        )

        # Valid (ON or OFF) for 10s. last_changed alone (t=8) would report not
        # met; history anchors to the start of the run, so the 5s `for:` is met.
        assert test.async_check() is True


async def test_state_condition_single_state_duration_skips_history(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A single-state condition uses last_changed directly and reads no history.

    `_needs_duration_tracking` is False for single-state, no-value_source
    conditions, so setup never sets up tracking or queries the recorder.
    """
    hass.states.async_set("test.entity_1", STATE_ON)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        return_value={},
    ) as mock_history:
        test = await _setup_state_condition(
            hass,
            states=STATE_ON,
            target_config={CONF_ENTITY_ID: ["test.entity_1"]},
            condition_options={CONF_FOR: {"seconds": 5}},
        )

    mock_history.assert_not_called()

    # The anchor comes straight from state.last_changed, so the duration is met.
    freezer.tick(timedelta(seconds=6))
    assert test.async_check() is True


class _AttributeBackedStateCondition(EntityConditionBase):
    """Test condition that reads an attribute directly in `is_valid_state`.

    Used by `test_state_condition_state_valid_since_anchors_duration` to
    drive the default `_state_valid_since` path (`last_changed`-anchored)
    for an attribute-source condition.
    """

    _domain_specs = {"test": DomainSpec()}

    def is_valid_state(self, entity_state: State) -> bool:
        return entity_state.attributes.get("flag") is True


class _AttributeBackedStateConditionLastUpdated(_AttributeBackedStateCondition):
    """Test condition that overrides `_state_valid_since` to use `last_updated`."""

    def _state_valid_since(self, state: State) -> datetime:
        return state.last_updated


@pytest.mark.parametrize(
    ("condition_cls", "duration_met_after_attr_flip"),
    [
        # Default `_state_valid_since` returns `last_changed` for the
        # state-source domain. With `state.state` unchanged for 60s, the
        # duration is satisfied as soon as the attribute flips —
        # demonstrates the false-positive bug for attribute-reading
        # conditions.
        (_AttributeBackedStateCondition, True),
        # Override returning `last_updated` resets the anchor on every
        # state update (including attribute-only updates), so the `for:`
        # window correctly starts at the moment of the flip.
        (_AttributeBackedStateConditionLastUpdated, False),
    ],
)
async def test_state_condition_state_valid_since_anchors_duration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    condition_cls: type[EntityConditionBase],
    duration_met_after_attr_flip: bool,
) -> None:
    """Verify `_state_valid_since` is consulted to anchor the `for:` duration.

    Drives a condition that becomes valid via an attribute flip while
    `state.state` is unchanged, then checks whether the duration is
    satisfied immediately after the flip. The result depends entirely on
    which timestamp `_state_valid_since` returns: the default
    (`last_changed`, far in the past) satisfies the duration immediately,
    while an override returning `last_updated` anchors to the flip and
    requires the full window to elapse.
    """

    async def async_get_conditions(
        hass: HomeAssistant,
    ) -> dict[str, type[Condition]]:
        return {"_": condition_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )

    # state.state is set well before the attribute flip — its
    # last_changed will be far in the past by the time the attribute
    # flips the condition true.
    hass.states.async_set("test.entity_1", STATE_ON, {"flag": False})
    await hass.async_block_till_done()

    config: dict[str, Any] = {
        CONF_CONDITION: "test",
        CONF_TARGET: {CONF_ENTITY_ID: "test.entity_1"},
        CONF_OPTIONS: {CONF_FOR: {"seconds": 5}},
    }
    config = await async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    assert test is not None

    freezer.tick(timedelta(seconds=60))

    hass.states.async_set("test.entity_1", STATE_ON, {"flag": True})
    await hass.async_block_till_done()

    # Just after the flip, well within the 5-second `for:` window.
    freezer.tick(timedelta(seconds=1))
    assert test.async_check() is duration_met_after_attr_flip


@pytest.mark.parametrize(("primary_entities_only"), [True, False])
async def test_state_condition_primary_entities_only(
    hass: HomeAssistant, primary_entities_only: bool
) -> None:
    """Test make_entity_state_condition primary_entities_only flag."""
    (
        area_id,
        primary_id,
        diagnostic_id,
    ) = await _create_primary_and_diagnostic_entities_in_area(hass, "test")

    test = await _setup_state_condition(
        hass,
        target_config={ATTR_AREA_ID: area_id},
        states=STATE_ON,
        condition_options={ATTR_BEHAVIOR: BEHAVIOR_ALL},
        primary_entities_only=primary_entities_only,
    )

    # Primary on, diagnostic off
    hass.states.async_set(primary_id, STATE_ON)
    hass.states.async_set(diagnostic_id, STATE_OFF)
    await hass.async_block_till_done()
    # If diagnostic is included (primary_entities_only=False),
    # behavior=all fails because the diagnostic entity is off.
    # If excluded, only the primary is checked and it's on.
    assert test.async_check() is primary_entities_only

    # Both on - true regardless of flag
    hass.states.async_set(diagnostic_id, STATE_ON)
    await hass.async_block_till_done()
    assert test.async_check() is True


@pytest.mark.parametrize(("primary_entities_only"), [True, False])
async def test_numerical_condition_primary_entities_only(
    hass: HomeAssistant,
    primary_entities_only: bool,
) -> None:
    """Test make_entity_numerical_condition primary_entities_only flag."""
    (
        area_id,
        primary_id,
        diagnostic_id,
    ) = await _create_primary_and_diagnostic_entities_in_area(hass, "test")

    test = await _setup_numerical_condition(
        hass,
        target_config={ATTR_AREA_ID: area_id},
        condition_options={
            "threshold": {"type": "above", "value": {"number": 50}},
            ATTR_BEHAVIOR: BEHAVIOR_ALL,
        },
        primary_entities_only=primary_entities_only,
    )

    # Primary above threshold, diagnostic below
    hass.states.async_set(primary_id, "75")
    hass.states.async_set(diagnostic_id, "25")
    await hass.async_block_till_done()
    # If diagnostic is included (primary_entities_only=False),
    # behavior=all fails because the diagnostic value is below
    # the threshold. If excluded, only the primary is
    # checked and it's above.
    assert test.async_check() is primary_entities_only

    # Both above threshold — true regardless of flag
    hass.states.async_set(diagnostic_id, "75")
    await hass.async_block_till_done()
    assert test.async_check() is True


@pytest.mark.parametrize(("primary_entities_only"), [True, False])
async def test_state_condition_primary_entities_only_with_duration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    primary_entities_only: bool,
) -> None:
    """Test make_entity_state_condition primary_entities_only flag with duration."""
    (
        area_id,
        primary_id,
        diagnostic_id,
    ) = await _create_primary_and_diagnostic_entities_in_area(hass, "test")

    # Primary starts with matching attribute, diagnostic with non-matching attribute
    hass.states.async_set(primary_id, STATE_ON, {"test_attr": True})
    hass.states.async_set(diagnostic_id, STATE_ON, {"test_attr": False})
    await hass.async_block_till_done()

    test = await _setup_state_condition(
        hass,
        target_config={ATTR_AREA_ID: area_id},
        states={True},
        domain_specs={"test": DomainSpec(value_source="test_attr")},
        condition_options={
            ATTR_BEHAVIOR: BEHAVIOR_ALL,
            CONF_FOR: {"seconds": 5},
        },
        primary_entities_only=primary_entities_only,
    )

    # 3s later, diagnostic transitions to matching. The state-change listener
    freezer.tick(timedelta(seconds=3))
    hass.states.async_set(diagnostic_id, STATE_ON, {"test_attr": True})
    await hass.async_block_till_done()

    # 3s after diagnostic became matching (6s total since primary became matching):
    # - primary_entities_only=True: diagnostic is excluded from evaluation,
    #   only primary is checked. Primary has been matching for 6s >= 5s → True.
    # - primary_entities_only=False: diagnostic is included. Diagnostic has
    #   only been matching for 3s < 5s → behavior=all is False.
    freezer.tick(timedelta(seconds=3))
    assert test.async_check() is primary_entities_only

    # 3 more seconds later (6s after diagnostic became matching). Now diagnostic
    # has also been matching for >= 5s → True regardless of flag.
    freezer.tick(timedelta(seconds=3))
    assert test.async_check() is True


async def test_async_from_config_calls_async_setup_on_checker(
    hass: HomeAssistant,
) -> None:
    """Test async_from_config calls async_setup on ConditionChecker."""

    class StubChecker(condition.ConditionChecker):
        """Stub checker to track async_setup calls."""

        def _async_check(self, **kwargs: Any) -> bool:
            return True

    stub = StubChecker(hass)

    async def fake_factory(
        hass: HomeAssistant, config: ConfigType
    ) -> condition.ConditionChecker:
        return stub

    with (
        patch.object(
            condition, "async_stub_checker_from_config", fake_factory, create=True
        ),
        patch.dict(condition._PLATFORM_ALIASES, {"stub_checker": None}),
    ):
        config = {"condition": "stub_checker"}
        config = cv.CONDITION_SCHEMA(config)
        result = await condition.async_from_config(hass, config)

    assert result is stub
    assert stub._set_up is True


async def test_async_setup_invokes_async_setup_hook(
    hass: HomeAssistant,
) -> None:
    """Test that async_setup awaits _async_setup and sets _set_up."""

    setup_hook = AsyncMock()

    class MockChecker(ConditionChecker):
        async def _async_setup(self) -> None:
            await setup_hook()

        def _async_check(self, **kwargs: Any) -> bool:
            return True

    checker = MockChecker(hass)

    assert checker._set_up is False
    setup_hook.assert_not_called()

    await checker.async_setup()

    setup_hook.assert_awaited_once()
    assert checker._set_up is True


async def test_async_check_raises_before_setup(
    hass: HomeAssistant,
) -> None:
    """Test that async_check raises HomeAssistantError before async_setup is called."""

    class MockChecker(ConditionChecker):
        def _async_check(self, **kwargs: Any) -> bool:
            return True

    checker = MockChecker(hass)

    with pytest.raises(HomeAssistantError, match="not set up"):
        checker.async_check()

    with pytest.raises(HomeAssistantError, match="not set up"):
        checker(hass)

    await checker.async_setup()

    assert checker.async_check() is True
    assert checker(hass) is True


async def test_async_unload_invokes_async_unload_hook(
    hass: HomeAssistant,
) -> None:
    """Test that async_unload calls _async_unload and sets _unloaded."""

    unload_hook = Mock()

    class MockChecker(ConditionChecker):
        def _async_unload(self) -> None:
            unload_hook()

        def _async_check(self, **kwargs: Any) -> bool:
            return True

    checker = MockChecker(hass)

    assert checker._unloaded is False
    unload_hook.assert_not_called()

    checker.async_unload()

    unload_hook.assert_called_once()
    assert checker._unloaded is True
