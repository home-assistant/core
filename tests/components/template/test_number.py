"""The tests for the Template number platform."""

from homeassistant import setup
from homeassistant.components.input_number import (
    ATTR_VALUE as INPUT_NUMBER_ATTR_VALUE,
    DOMAIN as INPUT_NUMBER_DOMAIN,
    SERVICE_SET_VALUE as INPUT_NUMBER_SERVICE_SET_VALUE,
)
from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE as NUMBER_ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE as NUMBER_SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ICON, CONF_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.entity_registry import async_get

from tests.common import assert_setup_component, async_capture_events

_TEST_NUMBER = "number.template_number"
# Represent for number's value
_VALUE_INPUT_NUMBER = "input_number.value"
# Represent for number's minimum
_MINIMUM_INPUT_NUMBER = "input_number.minimum"
# Represent for number's maximum
_MAXIMUM_INPUT_NUMBER = "input_number.maximum"
# Represent for number's step
_STEP_INPUT_NUMBER = "input_number.step"

# Config for `_VALUE_INPUT_NUMBER`
_VALUE_INPUT_NUMBER_CONFIG = {
    "value": {
        "min": 0.0,
        "max": 100.0,
        "name": "Value",
        "step": 1.0,
        "mode": "slider",
    }
}


async def test_missing_optional_config(hass: HomeAssistant) -> None:
    """Test: missing optional template is ok."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "number": {
                        "state": "{{ 4 }}",
                        "set_value": {"service": "script.set_value"},
                        "step": "{{ 1 }}",
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, 4, 1, 0.0, 100.0)


async def test_missing_required_keys(hass: HomeAssistant) -> None:
    """Test: missing required fields will fail."""
    with assert_setup_component(0, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "number": {
                        "set_value": {"service": "script.set_value"},
                    }
                }
            },
        )

    with assert_setup_component(0, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "number": {
                        "state": "{{ 4 }}",
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("number") == []


async def test_all_optional_config(hass: HomeAssistant) -> None:
    """Test: including all optional templates is ok."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "number": {
                        "state": "{{ 4 }}",
                        "set_value": {"service": "script.set_value"},
                        "min": "{{ 3 }}",
                        "max": "{{ 5 }}",
                        "step": "{{ 1 }}",
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, 4, 1, 3, 5)


async def test_templates_with_entities(hass: HomeAssistant, calls) -> None:
    """Test templates with values from other entities."""
    with assert_setup_component(4, "input_number"):
        assert await setup.async_setup_component(
            hass,
            "input_number",
            {
                "input_number": {
                    **_VALUE_INPUT_NUMBER_CONFIG,
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

    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "unique_id": "b",
                    "number": {
                        "state": f"{{{{ states('{_VALUE_INPUT_NUMBER}') }}}}",
                        "step": f"{{{{ states('{_STEP_INPUT_NUMBER}') }}}}",
                        "min": f"{{{{ states('{_MINIMUM_INPUT_NUMBER}') }}}}",
                        "max": f"{{{{ states('{_MAXIMUM_INPUT_NUMBER}') }}}}",
                        "set_value": [
                            {
                                "service": "input_number.set_value",
                                "data_template": {
                                    "entity_id": _VALUE_INPUT_NUMBER,
                                    "value": "{{ value }}",
                                },
                            },
                            {
                                "service": "test.automation",
                                "data_template": {
                                    "action": "set_value",
                                    "caller": "{{ this.entity_id }}",
                                    "value": "{{ value }}",
                                },
                            },
                        ],
                        "optimistic": True,
                        "unique_id": "a",
                    },
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

    ent_reg = async_get(hass)
    entry = ent_reg.async_get(_TEST_NUMBER)
    assert entry
    assert entry.unique_id == "b-a"

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

    # Check this variable can be used in set_value script
    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_value"
    assert calls[-1].data["caller"] == _TEST_NUMBER
    assert calls[-1].data["value"] == 2


async def test_trigger_number(hass: HomeAssistant) -> None:
    """Test trigger based template number."""
    events = async_capture_events(hass, "test_number_event")
    assert await setup.async_setup_component(
        hass,
        "template",
        {
            "template": [
                {"invalid": "config"},
                # Config after invalid should still be set up
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "number": [
                        {
                            "name": "Hello Name",
                            "unique_id": "hello_name-id",
                            "state": "{{ trigger.event.data.beers_drank }}",
                            "min": "{{ trigger.event.data.min_beers }}",
                            "max": "{{ trigger.event.data.max_beers }}",
                            "step": "{{ trigger.event.data.step }}",
                            "set_value": {"event": "test_number_event"},
                            "optimistic": True,
                        },
                    ],
                },
            ],
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("number.hello_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["min"] == 0.0
    assert state.attributes["max"] == 100.0
    assert state.attributes["step"] == 1.0

    context = Context()
    hass.bus.async_fire(
        "test_event",
        {"beers_drank": 3, "min_beers": 1.0, "max_beers": 5.0, "step": 0.5},
        context=context,
    )
    await hass.async_block_till_done()

    state = hass.states.get("number.hello_name")
    assert state is not None
    assert state.state == "3.0"
    assert state.attributes["min"] == 1.0
    assert state.attributes["max"] == 5.0
    assert state.attributes["step"] == 0.5

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {CONF_ENTITY_ID: "number.hello_name", NUMBER_ATTR_VALUE: 2},
        blocking=True,
    )
    assert len(events) == 1
    assert events[0].event_type == "test_number_event"


def _verify(
    hass,
    expected_value,
    expected_step,
    expected_minimum,
    expected_maximum,
):
    """Verify number's state."""
    state = hass.states.get(_TEST_NUMBER)
    attributes = state.attributes
    assert state.state == str(float(expected_value))
    assert attributes.get(ATTR_STEP) == float(expected_step)
    assert attributes.get(ATTR_MAX) == float(expected_maximum)
    assert attributes.get(ATTR_MIN) == float(expected_minimum)


async def test_icon_template(hass: HomeAssistant) -> None:
    """Test template numbers with icon templates."""
    with assert_setup_component(1, "input_number"):
        assert await setup.async_setup_component(
            hass,
            "input_number",
            {"input_number": _VALUE_INPUT_NUMBER_CONFIG},
        )

    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "unique_id": "b",
                    "number": {
                        "state": f"{{{{ states('{_VALUE_INPUT_NUMBER}') }}}}",
                        "step": 1,
                        "min": 0,
                        "max": 100,
                        "set_value": {
                            "service": "input_number.set_value",
                            "data_template": {
                                "entity_id": _VALUE_INPUT_NUMBER,
                                "value": "{{ value }}",
                            },
                        },
                        "icon": "{% if ((states.input_number.value.state or 0) | int) > 50 %}mdi:greater{% else %}mdi:less{% endif %}",
                    },
                }
            },
        )

    hass.states.async_set(_VALUE_INPUT_NUMBER, 49)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_NUMBER)
    assert float(state.state) == 49
    assert state.attributes[ATTR_ICON] == "mdi:less"

    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        INPUT_NUMBER_SERVICE_SET_VALUE,
        {CONF_ENTITY_ID: _VALUE_INPUT_NUMBER, INPUT_NUMBER_ATTR_VALUE: 51},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_NUMBER)
    assert float(state.state) == 51
    assert state.attributes[ATTR_ICON] == "mdi:greater"


async def test_icon_template_with_trigger(hass: HomeAssistant) -> None:
    """Test template numbers with icon templates."""
    with assert_setup_component(1, "input_number"):
        assert await setup.async_setup_component(
            hass,
            "input_number",
            {"input_number": _VALUE_INPUT_NUMBER_CONFIG},
        )

    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "trigger": {"platform": "state", "entity_id": _VALUE_INPUT_NUMBER},
                    "unique_id": "b",
                    "number": {
                        "state": "{{ trigger.to_state.state }}",
                        "step": 1,
                        "min": 0,
                        "max": 100,
                        "set_value": {
                            "service": "input_number.set_value",
                            "data_template": {
                                "entity_id": _VALUE_INPUT_NUMBER,
                                "value": "{{ value }}",
                            },
                        },
                        "icon": "{% if ((trigger.to_state.state or 0) | int) > 50 %}mdi:greater{% else %}mdi:less{% endif %}",
                    },
                }
            },
        )

    hass.states.async_set(_VALUE_INPUT_NUMBER, 49)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_NUMBER)
    assert float(state.state) == 49
    assert state.attributes[ATTR_ICON] == "mdi:less"

    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        INPUT_NUMBER_SERVICE_SET_VALUE,
        {CONF_ENTITY_ID: _VALUE_INPUT_NUMBER, INPUT_NUMBER_ATTR_VALUE: 51},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(_TEST_NUMBER)
    assert float(state.state) == 51
    assert state.attributes[ATTR_ICON] == "mdi:greater"
