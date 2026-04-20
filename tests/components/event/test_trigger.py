"""Test event trigger."""

import pytest

from homeassistant.components.event.const import ATTR_EVENT_TYPE
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
async def target_events(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple event entities associated with different targets."""
    return await target_entities(hass, "event")


@pytest.mark.parametrize("trigger_key", ["event.received"])
async def test_event_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the event triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(
        hass,
        caplog,
        trigger_key,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("event"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        # Event received with matching event_type
        (
            "event.received",
            {"event_type": ["button_press"]},
            [
                {"included_state": {"state": None, "attributes": {}}, "count": 0},
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
        # Event received with non-matching event_type then matching
        (
            "event.received",
            {"event_type": ["button_press"]},
            [
                {"included_state": {"state": None, "attributes": {}}, "count": 0},
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "other_event"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
        # Multiple event types configured
        (
            "event.received",
            {"event_type": ["button_press", "button_long_press"]},
            [
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_long_press"},
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:02.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "other_event"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:03.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
        # From unavailable - first valid state after unavailable is not triggered
        (
            "event.received",
            {"event_type": ["button_press"]},
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
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
        # From unknown - first valid state after unknown is triggered
        (
            "event.received",
            {"event_type": ["button_press"]},
            [
                {
                    "included_state": {
                        "state": STATE_UNKNOWN,
                        "attributes": {},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": STATE_UNKNOWN,
                        "attributes": {},
                    },
                    "count": 0,
                },
            ],
        ),
        # Same event type fires again (different timestamps)
        (
            "event.received",
            {"event_type": ["button_press"]},
            [
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:02.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
        # To unavailable - should not trigger, and first state after unavailable is skipped
        (
            "event.received",
            {"event_type": ["button_press"]},
            [
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": STATE_UNAVAILABLE,
                        "attributes": {},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:02.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
    ],
)
async def test_event_state_trigger(
    hass: HomeAssistant,
    target_events: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict,
    states: list[TriggerStateDescription],
) -> None:
    """Test that the event trigger fires when an event entity receives a matching event."""
    calls: list[str] = []
    other_entity_ids = set(target_events["included_entities"]) - {entity_id}

    # Set all events to the initial state
    for eid in target_events["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, trigger_options, trigger_target_config, calls)

    for state in states[1:]:
        included_state = state["included_state"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()

        # Check if changing other events also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(calls) == (entities_in_target - 1) * state["count"]
        calls.clear()
