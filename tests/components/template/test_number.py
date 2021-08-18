"""The tests for the Template fan platform."""
import pytest

from homeassistant import setup
from homeassistant.components.input_number import (
    ATTR_VALUE as INPUT_NUMBER_ATTR_VALUE,
    DOMAIN as INPUT_NUMBER_DOMAIN,
    SERVICE_SET_VALUE as INPUT_NUMBER_SERVICE_SET_VALUE,
)
from homeassistant.components.number.const import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE as NUMBER_ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE as NUMBER_SERVICE_SET_VALUE,
)
from homeassistant.const import CONF_ENTITY_ID

from tests.common import assert_setup_component, async_mock_service

_TEST_NUMBER = "number.template_number"
# Represent for number's value
_VALUE_INPUT_NUMBER = "input_number.value"
# Represent for number's minimum
_MINIMUM_INPUT_NUMBER = "input_number.minimum"
# Represent for number's maximum
_MAXIMUM_INPUT_NUMBER = "input_number.maximum"
# Represent for number's step
_STEP_INPUT_NUMBER = "input_number.step"


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_missing_optional_config(hass, calls):
    """Test: missing optional template is ok."""
    with assert_setup_component(1, "number"):
        assert await setup.async_setup_component(
            hass,
            "number",
            {
                "number": {
                    "platform": "template",
                    "value_template": "{{ 4 }}",
                    "set_value": {"service": "script.set_value"},
                    "step_template": "{{ 1 }}",
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, 4, 1, 0.0, 100.0)


async def test_missing_required_keys(hass, calls):
    """Test: missing required fields will fail."""
    with assert_setup_component(0, "number"):
        assert await setup.async_setup_component(
            hass,
            "number",
            {
                "number": {
                    "platform": "template",
                    "set_value": {"service": "script.set_value"},
                }
            },
        )

    with assert_setup_component(0, "number"):
        assert await setup.async_setup_component(
            hass,
            "number",
            {
                "number": {
                    "platform": "template",
                    "value_template": "{{ 4 }}",
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_all_optional_config(hass, calls):
    """Test: including all optional templates is ok."""
    with assert_setup_component(1, "number"):
        assert await setup.async_setup_component(
            hass,
            "number",
            {
                "number": {
                    "platform": "template",
                    "value_template": "{{ 4 }}",
                    "set_value": {"service": "script.set_value"},
                    "minimum_template": "{{ 3 }}",
                    "maximum_template": "{{ 5 }}",
                    "step_template": "{{ 1 }}",
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, 4, 1, 3, 5)


async def test_templates_with_entities(hass, calls):
    """Test tempalates with values from other entities."""
    with assert_setup_component(4, "input_number"):
        assert await setup.async_setup_component(
            hass,
            "input_number",
            {
                "input_number": {
                    "value": {
                        "min": 0.0,
                        "max": 100.0,
                        "name": "Value",
                        "step": 1.0,
                        "mode": "slider",
                    },
                    "step": {
                        "min": 0.0,
                        "max": 100.0,
                        "name": "Step",
                        "step": 1.0,
                        "mode": "slider",
                    },
                    "minimum": {
                        "min": 0.0,
                        "max": 100.0,
                        "name": "Minimum",
                        "step": 1.0,
                        "mode": "slider",
                    },
                    "maximum": {
                        "min": 0.0,
                        "max": 100.0,
                        "name": "Maximum",
                        "step": 1.0,
                        "mode": "slider",
                    },
                }
            },
        )

    with assert_setup_component(1, "number"):
        assert await setup.async_setup_component(
            hass,
            "number",
            {
                "number": {
                    "platform": "template",
                    "value_template": f"{{{{ states('{_VALUE_INPUT_NUMBER}') }}}}",
                    "step_template": f"{{{{ states('{_STEP_INPUT_NUMBER}') }}}}",
                    "minimum_template": f"{{{{ states('{_MINIMUM_INPUT_NUMBER}') }}}}",
                    "maximum_template": f"{{{{ states('{_MAXIMUM_INPUT_NUMBER}') }}}}",
                    "set_value": {
                        "service": "input_number.set_value",
                        "data_template": {
                            "entity_id": _VALUE_INPUT_NUMBER,
                            "value": "{{ value }}",
                        },
                    },
                    "optimistic": True,
                }
            },
        )

    hass.states.async_set(_VALUE_INPUT_NUMBER, 4)
    hass.states.async_set(_STEP_INPUT_NUMBER, 1)
    hass.states.async_set(_MINIMUM_INPUT_NUMBER, 3)
    hass.states.async_set(_MAXIMUM_INPUT_NUMBER, 5)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, 4, 1, 3, 5)

    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        INPUT_NUMBER_SERVICE_SET_VALUE,
        {CONF_ENTITY_ID: _VALUE_INPUT_NUMBER, INPUT_NUMBER_ATTR_VALUE: 5},
        blocking=True,
    )
    await hass.async_block_till_done()
    _verify(hass, 5, 1, 3, 5)

    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        INPUT_NUMBER_SERVICE_SET_VALUE,
        {CONF_ENTITY_ID: _STEP_INPUT_NUMBER, INPUT_NUMBER_ATTR_VALUE: 2},
        blocking=True,
    )
    await hass.async_block_till_done()
    _verify(hass, 5, 2, 3, 5)

    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        INPUT_NUMBER_SERVICE_SET_VALUE,
        {CONF_ENTITY_ID: _MINIMUM_INPUT_NUMBER, INPUT_NUMBER_ATTR_VALUE: 2},
        blocking=True,
    )
    await hass.async_block_till_done()
    _verify(hass, 5, 2, 2, 5)

    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        INPUT_NUMBER_SERVICE_SET_VALUE,
        {CONF_ENTITY_ID: _MAXIMUM_INPUT_NUMBER, INPUT_NUMBER_ATTR_VALUE: 6},
        blocking=True,
    )
    await hass.async_block_till_done()
    _verify(hass, 5, 2, 2, 6)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {CONF_ENTITY_ID: _TEST_NUMBER, NUMBER_ATTR_VALUE: 2},
        blocking=True,
    )
    _verify(hass, 2, 2, 2, 6)


def _verify(
    hass,
    expected_value,
    expected_step,
    expected_minimum,
    expected_maximum,
):
    """Verify fan's state, speed and osc."""
    state = hass.states.get(_TEST_NUMBER)
    attributes = state.attributes
    assert state.state == str(float(expected_value))
    assert attributes.get(ATTR_STEP) == float(expected_step)
    assert attributes.get(ATTR_MAX) == float(expected_maximum)
    assert attributes.get(ATTR_MIN) == float(expected_minimum)
