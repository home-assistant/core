"""Test button trigger."""

from collections.abc import Callable, Sequence
from datetime import timedelta
from typing import Any
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import async_fire_time_changed_exact
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
    ATTR_FRIENDLY_NAME,
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, label_registry as lr
from homeassistant.helpers.trigger import (
    NotTriggeredInfo,
    async_initialize_triggers,
    async_validate_trigger_config,
)
from homeassistant.helpers.typing import TemplateVarsType

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
    "held": TargetSupport.CUSTOM,
    "hold_ended": TargetSupport.STANDARD,
}


@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("button.pressed", None, False, False),
        ("button.held", None, False, False),
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


def test_trigger_target_support() -> None:
    """Certify the trigger registry matches its declared target support."""
    assert_triggers_target_support(TRIGGERS, _TRIGGER_TARGET_SUPPORT)


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        ({"milliseconds": 500}, timedelta(milliseconds=500)),
        ("00:00:01.5", timedelta(seconds=1.5)),
        (2, timedelta(seconds=2)),
        ({"seconds": 29.999}, timedelta(seconds=29.999)),
    ],
)
async def test_button_held_trigger_interval_valid(
    hass: HomeAssistant,
    interval: dict[str, float] | str | int,
    expected: timedelta,
) -> None:
    """Test the held trigger accepts an interval shorter than the hold timeout."""
    validated_config = await async_validate_trigger_config(
        hass,
        [
            {
                CONF_PLATFORM: "button.held",
                CONF_TARGET: {CONF_ENTITY_ID: _EVENT_ENTITY_ID},
                CONF_OPTIONS: {"interval": interval},
            }
        ],
    )
    assert validated_config[0][CONF_OPTIONS]["interval"] == expected


@pytest.mark.parametrize(
    "interval",
    [
        0,
        "00:00:00",
        {"seconds": -1},
        {"seconds": 30},
        "00:01:00",
        "not_a_duration",
        None,
    ],
)
async def test_button_held_trigger_interval_invalid(
    hass: HomeAssistant, interval: dict[str, int] | str | int | None
) -> None:
    """Test the held trigger rejects an interval that cannot repeat."""
    with pytest.raises(probatio.Invalid):
        await async_validate_trigger_config(
            hass,
            [
                {
                    CONF_PLATFORM: "button.held",
                    CONF_TARGET: {CONF_ENTITY_ID: _EVENT_ENTITY_ID},
                    CONF_OPTIONS: {"interval": interval},
                }
            ],
        )


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
    ("trigger", "states"),
    [
        pytest.param(
            "button.pressed",
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
            id="pressed_single_press_declared",
        ),
        pytest.param(
            "button.pressed",
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
            id="pressed_press_end_fallback",
        ),
        pytest.param(
            "button.pressed",
            _button_event_states(
                _PRESS_START_BUTTON_EVENT_TYPES,
                [
                    ("press_start", 1),
                    ("press_start", 1),
                    ("long_press_start", 0),
                ],
            ),
            id="pressed_press_start_fallback",
        ),
        pytest.param(
            "button.pressed",
            _button_event_states(
                _HOLD_BUTTON_EVENT_TYPES,
                [
                    ("long_press_start", 0),
                    ("long_press_end", 0),
                    ("press_end", 0),
                ],
            ),
            id="pressed_no_press_event_types",
        ),
        pytest.param(
            "button.pressed",
            _button_event_states([], [("single_press", 0), ("press_end", 0)]),
            id="pressed_empty_event_types",
        ),
        pytest.param(
            "button.pressed",
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
            id="pressed_unavailable",
        ),
        pytest.param(
            "button.pressed",
            _button_event_states(
                _ALL_BUTTON_EVENT_TYPES,
                [("single_press", 0)],
                device_class="doorbell",
            ),
            id="pressed_not_button_device_class",
        ),
        pytest.param(
            "button.held",
            _button_event_states(
                _ALL_BUTTON_EVENT_TYPES,
                [
                    ("press_start", 0),
                    ("long_press_start", 1),
                    ("long_press_end", 0),
                    ("press_end", 0),
                    ("single_press", 0),
                    ("multi_press", 0),
                    ("long_press_start", 1),
                    ("long_press_start", 1),
                ],
            ),
            id="held_long_press_start_declared",
        ),
        pytest.param(
            "button.held",
            _button_event_states(
                ["press_start", "press_end", "long_press_end"],
                [
                    ("press_start", 0),
                    ("press_end", 0),
                    ("long_press_end", 1),
                    ("long_press_end", 1),
                ],
            ),
            id="held_long_press_end_fallback",
        ),
        pytest.param(
            "button.held",
            _button_event_states(
                ["press_start", "press_end", "single_press", "multi_press"],
                [
                    ("press_start", 0),
                    ("press_end", 0),
                    ("single_press", 0),
                    ("long_press_start", 0),
                    ("long_press_end", 0),
                ],
            ),
            id="held_no_hold_event_types",
        ),
        pytest.param(
            "button.held",
            _button_event_states([], [("long_press_start", 0)]),
            id="held_empty_event_types",
        ),
        pytest.param(
            "button.held",
            [
                {
                    "included_state": _button_event_state(
                        STATE_UNAVAILABLE, _HOLD_BUTTON_EVENT_TYPES
                    ),
                    "count": 0,
                },
                {
                    "included_state": _button_event_state(
                        "2026-01-01T00:00:00.000+00:00",
                        _HOLD_BUTTON_EVENT_TYPES,
                        "long_press_start",
                    ),
                    "count": 0,
                },
                {
                    "included_state": _button_event_state(
                        "2026-01-01T00:00:01.000+00:00",
                        _HOLD_BUTTON_EVENT_TYPES,
                        "long_press_start",
                    ),
                    "count": 1,
                },
                {
                    "included_state": _button_event_state(
                        STATE_UNAVAILABLE, _HOLD_BUTTON_EVENT_TYPES
                    ),
                    "count": 0,
                },
            ],
            id="held_unavailable",
        ),
        pytest.param(
            "button.held",
            _button_event_states(
                _HOLD_BUTTON_EVENT_TYPES,
                [("long_press_start", 0)],
                device_class="doorbell",
            ),
            id="held_not_button_device_class",
        ),
        pytest.param(
            "button.hold_ended",
            _button_event_states(
                _ALL_BUTTON_EVENT_TYPES,
                [
                    ("press_start", 0),
                    ("long_press_start", 0),
                    ("long_press_end", 1),
                    ("press_end", 0),
                    ("single_press", 0),
                    ("multi_press", 0),
                    ("long_press_end", 1),
                    ("long_press_end", 1),
                ],
            ),
            id="hold_ended_hold_event_types_declared",
        ),
        pytest.param(
            "button.hold_ended",
            _button_event_states(
                ["press_start", "press_end", "long_press_end"],
                [("press_start", 0), ("press_end", 0), ("long_press_end", 0)],
            ),
            id="hold_ended_only_long_press_end_declared",
        ),
        pytest.param(
            "button.hold_ended",
            _button_event_states(
                ["press_start", "press_end", "long_press_start"],
                [("long_press_start", 0), ("long_press_end", 0)],
            ),
            id="hold_ended_only_long_press_start_declared",
        ),
        pytest.param(
            "button.hold_ended",
            _button_event_states([], [("long_press_end", 0)]),
            id="hold_ended_empty_event_types",
        ),
        pytest.param(
            "button.hold_ended",
            [
                {
                    "included_state": _button_event_state(
                        STATE_UNAVAILABLE, _HOLD_BUTTON_EVENT_TYPES
                    ),
                    "count": 0,
                },
                {
                    "included_state": _button_event_state(
                        "2026-01-01T00:00:00.000+00:00",
                        _HOLD_BUTTON_EVENT_TYPES,
                        "long_press_end",
                    ),
                    "count": 0,
                },
                {
                    "included_state": _button_event_state(
                        "2026-01-01T00:00:01.000+00:00",
                        _HOLD_BUTTON_EVENT_TYPES,
                        "long_press_end",
                    ),
                    "count": 1,
                },
                {
                    "included_state": _button_event_state(
                        STATE_UNAVAILABLE, _HOLD_BUTTON_EVENT_TYPES
                    ),
                    "count": 0,
                },
            ],
            id="hold_ended_unavailable",
        ),
        pytest.param(
            "button.hold_ended",
            _button_event_states(
                _HOLD_BUTTON_EVENT_TYPES,
                [("long_press_end", 0)],
                device_class="doorbell",
            ),
            id="hold_ended_not_button_device_class",
        ),
    ],
)
async def test_button_event_trigger(
    hass: HomeAssistant,
    target_entities_indirect: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[BasicTriggerStateDescription],
) -> None:
    """Test the trigger fires on the preferred button event type."""
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
    ("trigger", "event_types", "event_type", "expected_reports"),
    [
        pytest.param(
            "button.pressed",
            _HOLD_BUTTON_EVENT_TYPES,
            "long_press_start",
            [
                (
                    "entity_event_types_not_supported",
                    {
                        "entity_id": _EVENT_ENTITY_ID,
                        "event_types": _HOLD_BUTTON_EVENT_TYPES,
                    },
                )
            ],
            id="pressed_no_press_event_types",
        ),
        pytest.param(
            "button.pressed",
            [],
            "long_press_start",
            [
                (
                    "entity_event_types_not_supported",
                    {"entity_id": _EVENT_ENTITY_ID, "event_types": []},
                )
            ],
            id="pressed_empty_event_types",
        ),
        pytest.param(
            "button.pressed",
            _ALL_BUTTON_EVENT_TYPES,
            "long_press_start",
            [],
            id="pressed_supported_event_types",
        ),
        pytest.param(
            "button.held",
            ["press_start", "press_end"],
            "press_end",
            [
                (
                    "entity_event_types_not_supported",
                    {
                        "entity_id": _EVENT_ENTITY_ID,
                        "event_types": ["press_start", "press_end"],
                    },
                )
            ],
            id="held_no_hold_event_types",
        ),
        pytest.param(
            "button.held",
            [],
            "press_end",
            [
                (
                    "entity_event_types_not_supported",
                    {"entity_id": _EVENT_ENTITY_ID, "event_types": []},
                )
            ],
            id="held_empty_event_types",
        ),
        pytest.param(
            "button.held",
            _HOLD_BUTTON_EVENT_TYPES,
            "press_end",
            [],
            id="held_supported_event_types",
        ),
        pytest.param(
            "button.hold_ended",
            ["press_start", "press_end", "long_press_end"],
            "long_press_end",
            [
                (
                    "entity_event_types_not_supported",
                    {
                        "entity_id": _EVENT_ENTITY_ID,
                        "event_types": ["press_start", "press_end", "long_press_end"],
                    },
                )
            ],
            id="hold_ended_only_long_press_end_declared",
        ),
        pytest.param(
            "button.hold_ended",
            ["press_start", "press_end", "long_press_start"],
            "long_press_start",
            [
                (
                    "entity_event_types_not_supported",
                    {
                        "entity_id": _EVENT_ENTITY_ID,
                        "event_types": ["press_start", "press_end", "long_press_start"],
                    },
                )
            ],
            id="hold_ended_only_long_press_start_declared",
        ),
        pytest.param(
            "button.hold_ended",
            [],
            "long_press_end",
            [
                (
                    "entity_event_types_not_supported",
                    {"entity_id": _EVENT_ENTITY_ID, "event_types": []},
                )
            ],
            id="hold_ended_empty_event_types",
        ),
        pytest.param(
            "button.hold_ended",
            _HOLD_BUTTON_EVENT_TYPES,
            "long_press_start",
            [],
            id="hold_ended_supported_event_types",
        ),
    ],
)
async def test_button_event_trigger_not_triggered_reports(
    hass: HomeAssistant,
    trigger: str,
    event_types: list[str],
    event_type: str,
    expected_reports: list[tuple[str, dict[str, Any]]],
) -> None:
    """Test the trigger reports only unsupported button event types."""
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
                CONF_PLATFORM: trigger,
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
        _button_event_state("2026-01-01T00:00:00.000+00:00", event_types, event_type),
    )
    await hass.async_block_till_done()

    assert calls == []
    assert [(report.reason, report.data) for report in reports] == expected_reports

    unsub()


@pytest.mark.parametrize(
    ("trigger", "event_type"),
    [
        pytest.param("button.held", "long_press_start", id="held"),
        pytest.param("button.hold_ended", "long_press_end", id="hold_ended"),
    ],
)
@pytest.mark.parametrize("entity_id", ["button.test_button", "input_button.test"])
async def test_button_hold_triggers_ignore_buttons(
    hass: HomeAssistant, trigger: str, event_type: str, entity_id: str
) -> None:
    """Test the hold triggers do not fire for button and input_button entities."""
    calls: list[str] = []
    set_or_remove_state(
        hass, entity_id, _button_event_state(STATE_UNKNOWN, _HOLD_BUTTON_EVENT_TYPES)
    )
    await arm_trigger(hass, trigger, None, {CONF_ENTITY_ID: entity_id}, calls)

    # Attributes of a hold event, so only the domain filter can keep it out.
    set_or_remove_state(
        hass,
        entity_id,
        _button_event_state(
            "2026-01-01T00:00:00.000+00:00",
            _HOLD_BUTTON_EVENT_TYPES,
            event_type,
        ),
    )
    await hass.async_block_till_done()

    assert calls == []


type _TimelineStep = Callable[[HomeAssistant, FrozenDateTimeFactory, int], None]


def _make_event_step(
    event_type: str, event_types: Sequence[str] = tuple(_PHYSICAL_BUTTON_EVENT_TYPES)
) -> _TimelineStep:
    """Return a step reporting a button event."""

    def step(hass: HomeAssistant, freezer: FrozenDateTimeFactory, index: int) -> None:
        set_or_remove_state(
            hass,
            _EVENT_ENTITY_ID,
            _button_event_state(
                f"2026-01-01T00:00:{index:02d}.000+00:00",
                list(event_types),
                event_type,
            ),
        )

    return step


def _make_set_state_step(state: str | None) -> _TimelineStep:
    """Return a step setting the button state, or removing it if None."""

    def step(hass: HomeAssistant, freezer: FrozenDateTimeFactory, index: int) -> None:
        set_or_remove_state(
            hass,
            _EVENT_ENTITY_ID,
            {
                "state": state,
                "attributes": {
                    ATTR_DEVICE_CLASS: "button",
                    ATTR_EVENT_TYPES: _PHYSICAL_BUTTON_EVENT_TYPES,
                },
            },
        )

    return step


def _make_attribute_update_step() -> _TimelineStep:
    """Return a step changing an attribute without reporting a new event."""

    def step(hass: HomeAssistant, freezer: FrozenDateTimeFactory, index: int) -> None:
        state = hass.states.get(_EVENT_ENTITY_ID)
        assert state is not None
        hass.states.async_set(
            _EVENT_ENTITY_ID,
            state.state,
            {**state.attributes, ATTR_FRIENDLY_NAME: f"Button {index}"},
        )

    return step


def _make_wait_step(**kwargs: float) -> _TimelineStep:
    """Return a step advancing the time."""

    def step(hass: HomeAssistant, freezer: FrozenDateTimeFactory, index: int) -> None:
        freezer.tick(timedelta(**kwargs))
        async_fire_time_changed_exact(hass)

    return step


def _fired(calls: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Return the entity_id and repeat count of each recorded run."""
    return [(data["entity_id"], data["repeat_count"]) for data in calls]


def _noop() -> None:
    """Do nothing."""


async def _arm_held_trigger(
    hass: HomeAssistant,
    target: dict[str, Any],
    options: dict[str, Any],
    calls: list[dict[str, Any]],
    on_run: Callable[[], None] = _noop,
) -> Callable[[], None]:
    """Arm the held trigger and record the trigger data of each run."""

    @callback
    def action(run_variables: TemplateVarsType, context: Context | None = None) -> None:
        assert run_variables is not None
        calls.append(run_variables["trigger"])
        on_run()

    validated_config = await async_validate_trigger_config(
        hass,
        [
            {
                CONF_PLATFORM: "button.held",
                CONF_TARGET: target,
                CONF_OPTIONS: options,
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
    )
    assert unsub is not None
    return unsub


_INTERVAL_500MS = {"interval": {"milliseconds": 500}}


@pytest.mark.parametrize(
    ("options", "steps"),
    [
        pytest.param(
            _INTERVAL_500MS,
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(milliseconds=499), []),
                (_make_wait_step(milliseconds=1), [1]),
                (_make_wait_step(milliseconds=500), [2]),
                (_make_event_step("long_press_end"), []),
                (_make_wait_step(milliseconds=500), []),
            ],
            id="repeats_until_released",
        ),
        pytest.param(
            _INTERVAL_500MS,
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(milliseconds=400), []),
                (_make_event_step("long_press_end"), []),
                (_make_wait_step(milliseconds=500), []),
            ],
            id="released_before_first_interval",
        ),
        pytest.param(
            {},
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(seconds=5), []),
                (_make_event_step("long_press_end"), []),
            ],
            id="no_interval",
        ),
        pytest.param(
            _INTERVAL_500MS,
            [
                (_make_event_step("long_press_start", ["long_press_start"]), [0]),
                (_make_wait_step(milliseconds=500), []),
            ],
            id="only_long_press_start_declared",
        ),
        pytest.param(
            _INTERVAL_500MS,
            [
                (_make_event_step("long_press_end", ["long_press_end"]), [0]),
                (_make_wait_step(milliseconds=500), []),
            ],
            id="only_long_press_end_declared",
        ),
        pytest.param(
            {"interval": {"seconds": 10}},
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(seconds=10), [1]),
                (_make_wait_step(seconds=10), [2]),
                (_make_wait_step(seconds=10), []),
                (_make_wait_step(seconds=10), []),
            ],
            id="stops_after_timeout",
        ),
        pytest.param(
            _INTERVAL_500MS,
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(seconds=2), [1]),
                (_make_wait_step(milliseconds=499), []),
                (_make_wait_step(milliseconds=1), [2]),
            ],
            id="late_repeat_delays_next",
        ),
        pytest.param(
            {"interval": {"seconds": 10}},
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(seconds=35), []),
                (_make_wait_step(seconds=10), []),
            ],
            id="late_repeat_after_timeout_dropped",
        ),
        pytest.param(
            _INTERVAL_500MS,
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(milliseconds=500), [1]),
                (_make_set_state_step(STATE_UNAVAILABLE), []),
                (_make_wait_step(milliseconds=500), []),
            ],
            id="stops_when_unavailable",
        ),
        pytest.param(
            _INTERVAL_500MS,
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(milliseconds=500), [1]),
                (_make_set_state_step(None), []),
                (_make_wait_step(milliseconds=500), []),
            ],
            id="stops_when_removed",
        ),
        pytest.param(
            _INTERVAL_500MS,
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(milliseconds=500), [1]),
                (_make_event_step("press_start"), []),
                (_make_wait_step(milliseconds=500), []),
            ],
            id="stops_on_other_event_type",
        ),
        pytest.param(
            _INTERVAL_500MS,
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_attribute_update_step(), []),
                (_make_wait_step(milliseconds=500), [1]),
            ],
            id="attribute_update_keeps_repeating",
        ),
        pytest.param(
            _INTERVAL_500MS,
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(milliseconds=500), [1]),
                (_make_wait_step(milliseconds=200), []),
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(milliseconds=300), []),
                (_make_wait_step(milliseconds=200), [1]),
            ],
            id="new_hold_restarts_repeating",
        ),
        pytest.param(
            _INTERVAL_500MS,
            [
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(milliseconds=500), [1]),
                (_make_event_step("long_press_end"), []),
                (_make_event_step("long_press_start"), [0]),
                (_make_wait_step(milliseconds=500), [1]),
            ],
            id="repeat_count_resets_on_next_hold",
        ),
    ],
)
async def test_button_held_trigger_repeat(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    options: dict[str, Any],
    steps: list[tuple[_TimelineStep, list[int]]],
) -> None:
    """Test the held trigger repeats at the interval while held."""
    calls: list[dict[str, Any]] = []
    set_or_remove_state(
        hass,
        _EVENT_ENTITY_ID,
        _button_event_state(STATE_UNKNOWN, _PHYSICAL_BUTTON_EVENT_TYPES),
    )
    unsub = await _arm_held_trigger(
        hass, {CONF_ENTITY_ID: _EVENT_ENTITY_ID}, options, calls
    )

    for index, (step, expected_repeat_counts) in enumerate(steps):
        step(hass, freezer, index)
        await hass.async_block_till_done()
        assert _fired(calls) == [
            (_EVENT_ENTITY_ID, repeat_count) for repeat_count in expected_repeat_counts
        ]
        calls.clear()

    unsub()


async def test_button_held_trigger_repeats_per_entity(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test each held entity repeats on its own interval."""
    calls: list[dict[str, Any]] = []
    entity_1 = "event.button_1"
    entity_2 = "event.button_2"
    for entity_id in (entity_1, entity_2):
        set_or_remove_state(
            hass,
            entity_id,
            _button_event_state(STATE_UNKNOWN, _HOLD_BUTTON_EVENT_TYPES),
        )
    unsub = await _arm_held_trigger(
        hass, {CONF_ENTITY_ID: [entity_1, entity_2]}, _INTERVAL_500MS, calls
    )

    set_or_remove_state(
        hass,
        entity_1,
        _button_event_state(
            "2026-01-01T00:00:00.000+00:00",
            _HOLD_BUTTON_EVENT_TYPES,
            "long_press_start",
        ),
    )
    await hass.async_block_till_done()
    freezer.tick(timedelta(milliseconds=200))
    set_or_remove_state(
        hass,
        entity_2,
        _button_event_state(
            "2026-01-01T00:00:00.200+00:00",
            _HOLD_BUTTON_EVENT_TYPES,
            "long_press_start",
        ),
    )
    await hass.async_block_till_done()
    assert _fired(calls) == [(entity_1, 0), (entity_2, 0)]
    calls.clear()

    freezer.tick(timedelta(milliseconds=300))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert _fired(calls) == [(entity_1, 1)]
    calls.clear()

    set_or_remove_state(
        hass,
        entity_1,
        _button_event_state(
            "2026-01-01T00:00:00.500+00:00",
            _HOLD_BUTTON_EVENT_TYPES,
            "long_press_end",
        ),
    )
    await hass.async_block_till_done()
    freezer.tick(timedelta(milliseconds=200))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert _fired(calls) == [(entity_2, 1)]
    calls.clear()

    freezer.tick(timedelta(milliseconds=500))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert _fired(calls) == [(entity_2, 2)]

    unsub()


async def test_button_held_trigger_trigger_data(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test repeats carry the state of the event that started the hold."""
    trigger_data: list[dict[str, Any]] = []
    set_or_remove_state(
        hass,
        _EVENT_ENTITY_ID,
        _button_event_state(STATE_UNKNOWN, _HOLD_BUTTON_EVENT_TYPES),
    )
    unsub = await _arm_held_trigger(
        hass, {CONF_ENTITY_ID: _EVENT_ENTITY_ID}, _INTERVAL_500MS, trigger_data
    )

    set_or_remove_state(
        hass,
        _EVENT_ENTITY_ID,
        _button_event_state(
            "2026-01-01T00:00:00.000+00:00",
            _HOLD_BUTTON_EVENT_TYPES,
            "long_press_start",
        ),
    )
    await hass.async_block_till_done()
    freezer.tick(timedelta(milliseconds=500))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()

    held_state = hass.states.get(_EVENT_ENTITY_ID)
    assert [
        (
            data["entity_id"],
            data["from_state"].state,
            data["to_state"],
            data["repeat_count"],
            data["description"],
        )
        for data in trigger_data
    ] == [
        (
            _EVENT_ENTITY_ID,
            STATE_UNKNOWN,
            held_state,
            0,
            f"state of {_EVENT_ENTITY_ID}",
        ),
        (
            _EVENT_ENTITY_ID,
            STATE_UNKNOWN,
            held_state,
            1,
            f"hold of {_EVENT_ENTITY_ID}",
        ),
    ]

    unsub()


async def test_button_held_trigger_entity_removed_from_target(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test repeating stops when the entity is removed from the target."""
    calls: list[dict[str, Any]] = []
    label = label_registry.async_create("Held buttons")
    entry = entity_registry.async_get_or_create(
        domain="event", platform="test", unique_id="held_button"
    )
    entity_registry.async_update_entity(entry.entity_id, labels={label.label_id})
    set_or_remove_state(
        hass,
        entry.entity_id,
        _button_event_state(STATE_UNKNOWN, _HOLD_BUTTON_EVENT_TYPES),
    )
    unsub = await _arm_held_trigger(
        hass, {ATTR_LABEL_ID: label.label_id}, _INTERVAL_500MS, calls
    )

    set_or_remove_state(
        hass,
        entry.entity_id,
        _button_event_state(
            "2026-01-01T00:00:00.000+00:00",
            _HOLD_BUTTON_EVENT_TYPES,
            "long_press_start",
        ),
    )
    await hass.async_block_till_done()
    assert _fired(calls) == [(entry.entity_id, 0)]
    calls.clear()

    entity_registry.async_update_entity(entry.entity_id, labels=set())
    await hass.async_block_till_done()
    freezer.tick(timedelta(milliseconds=500))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert _fired(calls) == []

    unsub()


async def test_button_held_trigger_unsubscribe_stops_repeating(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test removing the trigger stops repeating."""
    calls: list[dict[str, Any]] = []
    set_or_remove_state(
        hass,
        _EVENT_ENTITY_ID,
        _button_event_state(STATE_UNKNOWN, _HOLD_BUTTON_EVENT_TYPES),
    )
    unsub = await _arm_held_trigger(
        hass, {CONF_ENTITY_ID: _EVENT_ENTITY_ID}, _INTERVAL_500MS, calls
    )

    set_or_remove_state(
        hass,
        _EVENT_ENTITY_ID,
        _button_event_state(
            "2026-01-01T00:00:00.000+00:00",
            _HOLD_BUTTON_EVENT_TYPES,
            "long_press_start",
        ),
    )
    await hass.async_block_till_done()
    assert _fired(calls) == [(_EVENT_ENTITY_ID, 0)]
    calls.clear()

    unsub()
    freezer.tick(timedelta(milliseconds=500))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert _fired(calls) == []


async def _hold_until_run_ends_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    ending_run: int,
    hold_ending_action: Callable[[Callable[[], None]], None],
) -> list[int]:
    """Hold the button for three intervals and return the repeat count of each run.

    Only the run at ending_run calls hold_ending_action, synchronously within the
    run, with the function that removes the trigger.
    """
    calls: list[dict[str, Any]] = []
    unsubs: list[Callable[[], None]] = []
    run_effects = [*([_noop] * ending_run), lambda: hold_ending_action(unsubs[0])]

    def on_run() -> None:
        run_effects[len(calls) - 1]()

    set_or_remove_state(
        hass,
        _EVENT_ENTITY_ID,
        _button_event_state(STATE_UNKNOWN, _HOLD_BUTTON_EVENT_TYPES),
    )
    unsubs.append(
        await _arm_held_trigger(
            hass, {CONF_ENTITY_ID: _EVENT_ENTITY_ID}, _INTERVAL_500MS, calls, on_run
        )
    )

    set_or_remove_state(
        hass,
        _EVENT_ENTITY_ID,
        _button_event_state(
            "2026-01-01T00:00:00.000+00:00",
            _HOLD_BUTTON_EVENT_TYPES,
            "long_press_start",
        ),
    )
    await hass.async_block_till_done()
    for _ in range(3):
        freezer.tick(timedelta(milliseconds=500))
        async_fire_time_changed_exact(hass)
        await hass.async_block_till_done()

    return [data["repeat_count"] for data in calls]


@pytest.mark.parametrize(
    "ending_run",
    [pytest.param(0, id="hold_start_run"), pytest.param(1, id="repeat_run")],
)
async def test_button_held_trigger_run_reports_release(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, ending_run: int
) -> None:
    """Test repeating stops when a run reports the release of the button."""

    def report_release(unsub: Callable[[], None]) -> None:
        set_or_remove_state(
            hass,
            _EVENT_ENTITY_ID,
            _button_event_state(
                "2026-01-01T00:00:59.000+00:00",
                _HOLD_BUTTON_EVENT_TYPES,
                "long_press_end",
            ),
        )

    assert await _hold_until_run_ends_it(
        hass, freezer, ending_run, report_release
    ) == list(range(ending_run + 1))


@pytest.mark.parametrize(
    "ending_run",
    [pytest.param(0, id="hold_start_run"), pytest.param(1, id="repeat_run")],
)
async def test_button_held_trigger_run_removes_trigger(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, ending_run: int
) -> None:
    """Test repeating stops when a run removes the trigger."""

    def remove_trigger(unsub: Callable[[], None]) -> None:
        unsub()

    assert await _hold_until_run_ends_it(
        hass, freezer, ending_run, remove_trigger
    ) == list(range(ending_run + 1))


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
