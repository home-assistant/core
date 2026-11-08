"""Test button trigger."""

from typing import Any
from unittest.mock import Mock

import pytest
from pytest_homeassistant.components.common import (
    BasicTriggerStateDescription,
    StateDescription,
    TargetSupport,
    arm_trigger,
    assert_trigger_options_supported,
    assert_triggers_target_support,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)

from homeassistant.components.button.trigger import TRIGGERS
from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.trigger import (
    NotTriggeredInfo,
    async_initialize_triggers,
    async_validate_trigger_config,
)

_ALL_BUTTON_EVENT_TYPES = [
    "press_start",
    "press_end",
    "long_press_start",
    "long_press_end",
    "single_press",
    "multi_press",
]
_PHYSICAL_BUTTON_EVENT_TYPES = [
    "press_start",
    "press_end",
    "long_press_start",
    "long_press_end",
]
_PRESS_START_BUTTON_EVENT_TYPES = ["press_start", "long_press_start"]
_HOLD_BUTTON_EVENT_TYPES = ["long_press_start", "long_press_end"]
_EVENT_ENTITY_ID = "event.test_button"


def _button_event_state(
    state: str,
    event_types: list[str],
    event_type: str | None = None,
    device_class: str = "button",
) -> StateDescription:
    """Build an event entity state."""
    return {
        "state": state,
        "attributes": {
            ATTR_DEVICE_CLASS: device_class,
            ATTR_EVENT_TYPES: event_types,
            ATTR_EVENT_TYPE: event_type,
        },
    }


def _button_event_states(
    event_types: list[str],
    events: list[tuple[str, int]],
    device_class: str = "button",
) -> list[BasicTriggerStateDescription]:
    """Build an unknown initial state followed by events and their call counts."""
    return [
        {
            "included_state": _button_event_state(
                STATE_UNKNOWN, event_types, device_class=device_class
            ),
            "count": 0,
        },
        *(
            {
                "included_state": _button_event_state(
                    f"2026-01-01T00:00:{second:02d}.000+00:00",
                    event_types,
                    event_type,
                    device_class,
                ),
                "count": count,
            }
            for second, (event_type, count) in enumerate(events)
        ),
    ]


@pytest.fixture
async def target_entities_indirect(
    request: pytest.FixtureRequest, hass: HomeAssistant
) -> dict[str, list[str]]:
    """Create multiple entities associated with different targets."""
    return await target_entities(hass, request.param)


_TRIGGER_TARGET_SUPPORT: dict[str, TargetSupport] = {
    "pressed": TargetSupport.STANDARD,
}


@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("button.pressed", None, False, False),
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


def test_trigger_target_support() -> None:
    """Certify the trigger registry matches its declared target support."""
    assert_triggers_target_support(TRIGGERS, _TRIGGER_TARGET_SUPPORT)


@pytest.mark.parametrize(
    (
        "target_entities_indirect",
        "trigger_target_config",
        "entity_id",
        "entities_in_target",
    ),
    [
        *[
            ("button", config, entity_id, entities)
            for (config, entity_id, entities) in parametrize_target_entities("button")
        ],
        *[
            ("input_button", config, entity_id, entities)
            for (config, entity_id, entities) in parametrize_target_entities(
                "input_button"
            )
        ],
    ],
    indirect=["target_entities_indirect"],
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
    target_entities_indirect: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[BasicTriggerStateDescription],
) -> None:
    """Test that the button state trigger fires when targeted button state changes."""
    await _assert_trigger_fires(
        hass,
        target_entities=target_entities_indirect,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        states=states,
    )


@pytest.mark.parametrize(
    (
        "target_entities_indirect",
        "trigger_target_config",
        "entity_id",
        "entities_in_target",
    ),
    [("event", *params) for params in parametrize_target_entities("event")],
    indirect=["target_entities_indirect"],
)
@pytest.mark.parametrize(
    "states",
    [
        pytest.param(
            _button_event_states(
                _ALL_BUTTON_EVENT_TYPES,
                [
                    ("press_start", 0),
                    ("press_end", 0),
                    ("single_press", 1),
                    ("single_press", 1),
                    ("multi_press", 0),
                    ("long_press_start", 0),
                    ("long_press_end", 0),
                ],
            ),
            id="single_press_declared",
        ),
        pytest.param(
            _button_event_states(
                _PHYSICAL_BUTTON_EVENT_TYPES,
                [
                    ("press_start", 0),
                    ("press_end", 1),
                    ("press_end", 1),
                    ("long_press_start", 0),
                    ("long_press_end", 0),
                ],
            ),
            id="press_end_fallback",
        ),
        pytest.param(
            _button_event_states(
                _PRESS_START_BUTTON_EVENT_TYPES,
                [
                    ("press_start", 1),
                    ("press_start", 1),
                    ("long_press_start", 0),
                ],
            ),
            id="press_start_fallback",
        ),
        pytest.param(
            _button_event_states(
                _HOLD_BUTTON_EVENT_TYPES,
                [
                    ("long_press_start", 0),
                    ("long_press_end", 0),
                    ("press_end", 0),
                ],
            ),
            id="no_press_event_types",
        ),
        pytest.param(
            _button_event_states([], [("single_press", 0), ("press_end", 0)]),
            id="empty_event_types",
        ),
        pytest.param(
            [
                {
                    "included_state": _button_event_state(
                        STATE_UNAVAILABLE, _ALL_BUTTON_EVENT_TYPES
                    ),
                    "count": 0,
                },
                {
                    "included_state": _button_event_state(
                        "2026-01-01T00:00:00.000+00:00",
                        _ALL_BUTTON_EVENT_TYPES,
                        "single_press",
                    ),
                    "count": 0,
                },
                {
                    "included_state": _button_event_state(
                        "2026-01-01T00:00:01.000+00:00",
                        _ALL_BUTTON_EVENT_TYPES,
                        "single_press",
                    ),
                    "count": 1,
                },
                {
                    "included_state": _button_event_state(
                        STATE_UNAVAILABLE, _ALL_BUTTON_EVENT_TYPES
                    ),
                    "count": 0,
                },
                {
                    "included_state": _button_event_state(
                        "2026-01-01T00:00:02.000+00:00",
                        _ALL_BUTTON_EVENT_TYPES,
                        "single_press",
                    ),
                    "count": 0,
                },
            ],
            id="unavailable",
        ),
        pytest.param(
            _button_event_states(
                _ALL_BUTTON_EVENT_TYPES,
                [("single_press", 0)],
                device_class="doorbell",
            ),
            id="not_button_device_class",
        ),
    ],
)
async def test_button_event_pressed_trigger(
    hass: HomeAssistant,
    target_entities_indirect: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    states: list[BasicTriggerStateDescription],
) -> None:
    """Test the pressed trigger fires on the preferred button event type."""
    await _assert_trigger_fires(
        hass,
        target_entities=target_entities_indirect,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger="button.pressed",
        states=states,
    )


@pytest.mark.parametrize(
    ("event_types", "expected_reports"),
    [
        pytest.param(
            _HOLD_BUTTON_EVENT_TYPES,
            [
                (
                    "entity_event_types_not_supported",
                    {
                        "entity_id": _EVENT_ENTITY_ID,
                        "event_types": _HOLD_BUTTON_EVENT_TYPES,
                    },
                )
            ],
            id="no_press_event_types",
        ),
        pytest.param(
            [],
            [
                (
                    "entity_event_types_not_supported",
                    {"entity_id": _EVENT_ENTITY_ID, "event_types": []},
                )
            ],
            id="empty_event_types",
        ),
        pytest.param(_ALL_BUTTON_EVENT_TYPES, [], id="supported_event_types"),
    ],
)
async def test_button_event_pressed_trigger_not_triggered_reports(
    hass: HomeAssistant,
    event_types: list[str],
    expected_reports: list[tuple[str, dict[str, Any]]],
) -> None:
    """Test the pressed trigger reports only unsupported button event types."""
    calls: list[dict[str, Any]] = []
    reports: list[NotTriggeredInfo] = []

    @callback
    def action(run_variables: dict[str, Any], context: Context | None = None) -> None:
        calls.append(run_variables)

    @callback
    def did_not_trigger(
        run_variables: dict[str, Any],
        info: NotTriggeredInfo,
        context: Context | None = None,
    ) -> None:
        reports.append(info)

    set_or_remove_state(
        hass, _EVENT_ENTITY_ID, _button_event_state(STATE_UNKNOWN, event_types)
    )
    validated_config = await async_validate_trigger_config(
        hass,
        [
            {
                CONF_PLATFORM: "button.pressed",
                CONF_TARGET: {CONF_ENTITY_ID: _EVENT_ENTITY_ID},
            }
        ],
    )
    unsub = await async_initialize_triggers(
        hass,
        validated_config,
        action,
        domain="test",
        name="test_trigger",
        log_cb=Mock(),
        did_not_trigger=did_not_trigger,
    )
    assert unsub is not None

    set_or_remove_state(
        hass,
        _EVENT_ENTITY_ID,
        _button_event_state(
            "2026-01-01T00:00:00.000+00:00", event_types, "long_press_start"
        ),
    )
    await hass.async_block_till_done()

    assert calls == []
    assert [(report.reason, report.data) for report in reports] == expected_reports

    unsub()


async def _assert_trigger_fires(
    hass: HomeAssistant,
    target_entities: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[BasicTriggerStateDescription],
) -> None:
    """Assert that the trigger fires when targeted entity states change."""
    calls: list[str] = []
    other_entity_ids = set(target_entities["included_entities"]) - {entity_id}

    # Set all entities, including the tested entity, to the initial state
    for eid in target_entities["included_entities"]:
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

        # Check if changing other entities also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(calls) == (entities_in_target - 1) * state["count"]
        calls.clear()
