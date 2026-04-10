"""Test text trigger."""

import pytest

from homeassistant.components.input_text import DOMAIN as INPUT_TEXT_DOMAIN
from homeassistant.components.text.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.components.common import (
    BasicTriggerStateDescription,
    arm_trigger,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)

TEST_TRIGGER_STATES = [
    (
        "text.changed",
        [
            {
                "included_state": {"state": None, "attributes": {}},
                "count": 0,
            },
            {
                "included_state": {"state": "bar", "attributes": {}},
                "count": 0,
            },
            {
                "included_state": {"state": "baz", "attributes": {}},
                "count": 1,
            },
        ],
    ),
    (
        "text.changed",
        [
            {
                "included_state": {"state": "foo", "attributes": {}},
                "count": 0,
            },
            {
                "included_state": {"state": "bar", "attributes": {}},
                "count": 1,
            },
            {
                "included_state": {"state": "baz", "attributes": {}},
                "count": 1,
            },
        ],
    ),
    (
        "text.changed",
        [
            {
                "included_state": {"state": "foo", "attributes": {}},
                "count": 0,
            },
            # empty string
            {
                "included_state": {"state": "", "attributes": {}},
                "count": 1,
            },
            {
                "included_state": {"state": "baz", "attributes": {}},
                "count": 1,
            },
        ],
    ),
    (
        "text.changed",
        [
            {
                "included_state": {"state": STATE_UNAVAILABLE, "attributes": {}},
                "count": 0,
            },
            {
                "included_state": {"state": "bar", "attributes": {}},
                "count": 0,
            },
            {
                "included_state": {"state": "baz", "attributes": {}},
                "count": 1,
            },
            {
                "included_state": {"state": STATE_UNAVAILABLE, "attributes": {}},
                "count": 0,
            },
        ],
    ),
    (
        "text.changed",
        [
            {
                "included_state": {"state": STATE_UNKNOWN, "attributes": {}},
                "count": 0,
            },
            {
                "included_state": {"state": "bar", "attributes": {}},
                "count": 0,
            },
            {
                "included_state": {"state": "baz", "attributes": {}},
                "count": 1,
            },
            {
                "included_state": {"state": STATE_UNKNOWN, "attributes": {}},
                "count": 0,
            },
        ],
    ),
]


@pytest.fixture
async def target_texts(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple text entities associated with different targets."""
    return await target_entities(hass, DOMAIN)


@pytest.fixture
async def target_input_texts(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple input_text entities associated with different targets."""
    return await target_entities(hass, INPUT_TEXT_DOMAIN)


@pytest.mark.parametrize("trigger_key", ["text.changed"])
async def test_text_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the text triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(("trigger", "states"), TEST_TRIGGER_STATES)
async def test_text_state_trigger(
    hass: HomeAssistant,
    target_texts: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[BasicTriggerStateDescription],
) -> None:
    """Test that the text state trigger fires when targeted text state changes."""
    calls: list[str] = []
    other_entity_ids = set(target_texts["included_entities"]) - {entity_id}

    # Set all texts, including the tested text, to the initial state
    for eid in target_texts["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
    await hass.async_block_till_done()

    await arm_trigger(hass, trigger, None, trigger_target_config, calls)

    for state in states[1:]:
        included_state = state["included_state"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()

        # Check if changing other texts also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == (entities_in_target - 1) * state["count"]
        calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(INPUT_TEXT_DOMAIN),
)
@pytest.mark.parametrize(("trigger", "states"), TEST_TRIGGER_STATES)
async def test_input_text_state_trigger(
    hass: HomeAssistant,
    target_input_texts: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[BasicTriggerStateDescription],
) -> None:
    """Test that the `text.changed` trigger fires when any input_text entity's state changes."""
    calls: list[str] = []
    other_entity_ids = set(target_input_texts["included_entities"]) - {entity_id}

    # Set all input_texts, including the tested input_text, to the initial state
    for eid in target_input_texts["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
    await hass.async_block_till_done()

    await arm_trigger(hass, trigger, None, trigger_target_config, calls)

    for state in states[1:]:
        included_state = state["included_state"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()

        # Check if changing other input_texts also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == (entities_in_target - 1) * state["count"]
        calls.clear()
