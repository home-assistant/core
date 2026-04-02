"""Test button trigger."""

import pytest

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_buttons(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple button entities associated with different targets."""
    return await target_entities(hass, "button")


@pytest.mark.parametrize("trigger_key", ["button.pressed"])
async def test_button_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the button triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("button"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        (
            "button.pressed",
            [
                {
                    "included_state": {"state": None, "attributes": {}},
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2021-01-01T23:59:59+00:00",
                        "attributes": {},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2022-01-01T23:59:59+00:00",
                        "attributes": {},
                    },
                    "count": 1,
                },
            ],
        ),
        (
            "button.pressed",
            [
                {
                    "included_state": {"state": "foo", "attributes": {}},
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2021-01-01T23:59:59+00:00",
                        "attributes": {},
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": "2022-01-01T23:59:59+00:00",
                        "attributes": {},
                    },
                    "count": 1,
                },
            ],
        ),
        (
            "button.pressed",
            [
                {
                    "included_state": {
                        "state": STATE_UNAVAILABLE,
                        "attributes": {},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2021-01-01T23:59:59+00:00",
                        "attributes": {},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2022-01-01T23:59:59+00:00",
                        "attributes": {},
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": STATE_UNAVAILABLE,
                        "attributes": {},
                    },
                    "count": 0,
                },
            ],
        ),
        (
            "button.pressed",
            [
                {
                    "included_state": {"state": STATE_UNKNOWN, "attributes": {}},
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2021-01-01T23:59:59+00:00",
                        "attributes": {},
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": "2022-01-01T23:59:59+00:00",
                        "attributes": {},
                    },
                    "count": 1,
                },
                {
                    "included_state": {"state": STATE_UNKNOWN, "attributes": {}},
                    "count": 0,
                },
            ],
        ),
    ],
)
async def test_button_state_trigger(
    hass: HomeAssistant,
    target_buttons: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[TriggerStateDescription],
) -> None:
    """Test that the button state trigger fires when targeted button state changes."""
    calls: list[str] = []
    other_entity_ids = set(target_buttons["included_entities"]) - {entity_id}

    # Set all buttons, including the tested button, to the initial state
    for eid in target_buttons["included_entities"]:
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

        # Check if changing other buttons also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(calls) == (entities_in_target - 1) * state["count"]
        calls.clear()
