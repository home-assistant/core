"""Test button trigger."""

from typing import Any

import pytest

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.components.common import (
    BasicTriggerStateDescription,
    StateDescription,
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_options_supported,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)

_UNKNOWN_BUTTON_EVENT_STATE: StateDescription = {
    "state": STATE_UNKNOWN,
    "attributes": {ATTR_DEVICE_CLASS: "button"},
}
_UNAVAILABLE_BUTTON_EVENT_STATE: StateDescription = {
    "state": STATE_UNAVAILABLE,
    "attributes": {ATTR_DEVICE_CLASS: "button"},
}


def _button_event_state(
    second: int, event_type: str, **attributes: Any
) -> StateDescription:
    """Build a button event entity state with the given seconds in the state timestamp."""
    return {
        "state": f"2026-01-01T00:00:{second:02d}.000+00:00",
        "attributes": {
            ATTR_DEVICE_CLASS: "button",
            ATTR_EVENT_TYPE: event_type,
            **attributes,
        },
    }


@pytest.fixture
async def target_buttons(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple button entities associated with different targets."""
    return await target_entities(hass, "button")


@pytest.fixture
async def target_events(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple event entities associated with different targets."""
    return await target_entities(hass, "event")


@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("button.pressed", None, False, False),
        ("button.double_pressed", None, False, False),
        ("button.hold_started", None, False, False),
        ("button.hold_ended", None, False, False),
    ],
)
async def test_button_trigger_options_validation(
    hass: HomeAssistant,
    trigger_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that button triggers support the expected options."""
    await assert_trigger_options_supported(
        hass,
        trigger_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


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


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("event"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        # Only press_end fires the pressed trigger
        (
            "button.pressed",
            [
                {"included_state": _UNKNOWN_BUTTON_EVENT_STATE, "count": 0},
                {"included_state": _button_event_state(0, "press_start"), "count": 0},
                {"included_state": _button_event_state(1, "press_end"), "count": 1},
                {"included_state": _button_event_state(2, "press_end"), "count": 1},
                {
                    "included_state": _button_event_state(
                        3, "multi_press_end", multi_press_count=2
                    ),
                    "count": 0,
                },
                {
                    "included_state": _button_event_state(4, "long_press_start"),
                    "count": 0,
                },
                {
                    "included_state": _button_event_state(5, "long_press_end"),
                    "count": 0,
                },
            ],
        ),
        # To unavailable - should not trigger, and first state
        # after unavailable is skipped
        (
            "button.pressed",
            [
                {"included_state": _UNAVAILABLE_BUTTON_EVENT_STATE, "count": 0},
                {"included_state": _button_event_state(0, "press_end"), "count": 0},
                {"included_state": _button_event_state(1, "press_end"), "count": 1},
                {"included_state": _UNAVAILABLE_BUTTON_EVENT_STATE, "count": 0},
                {"included_state": _button_event_state(2, "press_end"), "count": 0},
                {"included_state": _button_event_state(3, "press_end"), "count": 1},
            ],
        ),
        # Event entities without the button device class are not tracked
        (
            "button.pressed",
            [
                {
                    "included_state": {
                        "state": STATE_UNKNOWN,
                        "attributes": {ATTR_DEVICE_CLASS: "doorbell"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "press_end",
                        },
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "press_end",
                        },
                    },
                    "count": 0,
                },
            ],
        ),
        # Only multi_press_end with a multi_press_count of 2 fires
        (
            "button.double_pressed",
            [
                {"included_state": _UNKNOWN_BUTTON_EVENT_STATE, "count": 0},
                {
                    "included_state": _button_event_state(
                        0, "multi_press_end", multi_press_count=2
                    ),
                    "count": 1,
                },
                {
                    "included_state": _button_event_state(
                        1, "multi_press_end", multi_press_count=3
                    ),
                    "count": 0,
                },
                {
                    "included_state": _button_event_state(
                        2, "multi_press_ongoing", multi_press_count=2
                    ),
                    "count": 0,
                },
                {"included_state": _button_event_state(3, "press_end"), "count": 0},
                {
                    "included_state": _button_event_state(
                        4, "multi_press_end", multi_press_count=2
                    ),
                    "count": 1,
                },
            ],
        ),
        # Only long_press_start fires the hold started trigger
        (
            "button.hold_started",
            [
                {"included_state": _UNKNOWN_BUTTON_EVENT_STATE, "count": 0},
                {
                    "included_state": _button_event_state(0, "long_press_start"),
                    "count": 1,
                },
                {
                    "included_state": _button_event_state(1, "long_press_end"),
                    "count": 0,
                },
                {"included_state": _button_event_state(2, "press_start"), "count": 0},
                {
                    "included_state": _button_event_state(3, "long_press_start"),
                    "count": 1,
                },
            ],
        ),
        # Only long_press_end fires the hold ended trigger
        (
            "button.hold_ended",
            [
                {"included_state": _UNKNOWN_BUTTON_EVENT_STATE, "count": 0},
                {
                    "included_state": _button_event_state(0, "long_press_start"),
                    "count": 0,
                },
                {
                    "included_state": _button_event_state(1, "long_press_end"),
                    "count": 1,
                },
                {"included_state": _button_event_state(2, "press_end"), "count": 0},
                {
                    "included_state": _button_event_state(3, "long_press_end"),
                    "count": 1,
                },
            ],
        ),
    ],
)
async def test_button_event_trigger(
    hass: HomeAssistant,
    target_events: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[BasicTriggerStateDescription],
) -> None:
    """Test that button triggers fire on standardized button event entity events."""
    calls: list[str] = []
    other_entity_ids = set(target_events["included_entities"]) - {entity_id}

    # Set all events to the initial state
    for eid in target_events["included_entities"]:
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

        # Check if changing other events also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(calls) == (entities_in_target - 1) * state["count"]
        calls.clear()
