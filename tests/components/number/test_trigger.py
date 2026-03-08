"""Test number entity trigger."""

import pytest

from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.number.const import DOMAIN
from homeassistant.const import (
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components import (
    TriggerStateDescription,
    arm_trigger,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_numbers(hass: HomeAssistant) -> list[str]:
    """Create multiple number entities associated with different targets."""
    return (await target_entities(hass, DOMAIN))["included"]


@pytest.fixture
async def target_input_numbers(hass: HomeAssistant) -> list[str]:
    """Create multiple input number entities associated with different targets."""
    return (await target_entities(hass, INPUT_NUMBER_DOMAIN))["included"]


@pytest.mark.parametrize(
    "trigger_key",
    [
        "number.changed",
    ],
)
async def test_number_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the number entity triggers are gated by the labs flag."""
    await arm_trigger(hass, trigger_key, None, {ATTR_LABEL_ID: "test_label"})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger_key}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        (
            "number.changed",
            [
                {"included": {"state": None, "attributes": {}}, "count": 0},
                {"included": {"state": "1", "attributes": {}}, "count": 0},
                {"included": {"state": "2", "attributes": {}}, "count": 1},
            ],
        ),
        (
            "number.changed",
            [
                {"included": {"state": "1", "attributes": {}}, "count": 0},
                {"included": {"state": "1.1", "attributes": {}}, "count": 1},
                {"included": {"state": "1", "attributes": {}}, "count": 1},
                {"included": {"state": None, "attributes": {}}, "count": 0},
                {"included": {"state": "2", "attributes": {}}, "count": 0},
                {"included": {"state": "1.5", "attributes": {}}, "count": 1},
            ],
        ),
        (
            "number.changed",
            [
                {"included": {"state": "1", "attributes": {}}, "count": 0},
                {"included": {"state": "not a number", "attributes": {}}, "count": 0},
                {"included": {"state": "2", "attributes": {}}, "count": 1},
            ],
        ),
        (
            "number.changed",
            [
                {
                    "included": {"state": STATE_UNAVAILABLE, "attributes": {}},
                    "count": 0,
                },
                {"included": {"state": "1", "attributes": {}}, "count": 0},
                {"included": {"state": "2", "attributes": {}}, "count": 1},
                {
                    "included": {"state": STATE_UNAVAILABLE, "attributes": {}},
                    "count": 0,
                },
            ],
        ),
        (
            "number.changed",
            [
                {"included": {"state": STATE_UNKNOWN, "attributes": {}}, "count": 0},
                {"included": {"state": "1", "attributes": {}}, "count": 0},
                {"included": {"state": "2", "attributes": {}}, "count": 1},
                {"included": {"state": STATE_UNKNOWN, "attributes": {}}, "count": 0},
            ],
        ),
    ],
)
async def test_number_changed_trigger_behavior(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_numbers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[TriggerStateDescription],
) -> None:
    """Test that the number changed trigger behaves correctly."""
    other_entity_ids = set(target_numbers) - {entity_id}

    # Set all numbers, including the tested number, to the initial state
    for eid in target_numbers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, None, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check that changing other numbers also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(INPUT_NUMBER_DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        (
            "number.changed",
            [
                {"included": {"state": None, "attributes": {}}, "count": 0},
                {"included": {"state": "1", "attributes": {}}, "count": 0},
                {"included": {"state": "2", "attributes": {}}, "count": 1},
            ],
        ),
        (
            "number.changed",
            [
                {"included": {"state": "1", "attributes": {}}, "count": 0},
                {"included": {"state": "1.1", "attributes": {}}, "count": 1},
                {"included": {"state": "1", "attributes": {}}, "count": 1},
                {"included": {"state": None, "attributes": {}}, "count": 0},
                {"included": {"state": "2", "attributes": {}}, "count": 0},
                {"included": {"state": "1.5", "attributes": {}}, "count": 1},
            ],
        ),
        (
            "number.changed",
            [
                {"included": {"state": "1", "attributes": {}}, "count": 0},
                {"included": {"state": "not a number", "attributes": {}}, "count": 0},
                {"included": {"state": "2", "attributes": {}}, "count": 1},
            ],
        ),
    ],
)
async def test_input_number_changed_trigger_behavior(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_input_numbers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[TriggerStateDescription],
) -> None:
    """Test that the input_number changed trigger behaves correctly."""
    other_entity_ids = set(target_input_numbers) - {entity_id}

    # Set all input_numbers, including the tested input_number, to the initial state
    for eid in target_input_numbers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, None, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check that changing other input_numbers also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()
