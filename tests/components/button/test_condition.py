"""Test button conditions."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.components.common import (
    ConditionStateDescription,
    TargetSupport,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_options_supported,
    assert_conditions_target_support,
    create_target_condition,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)

from homeassistant.components.button.condition import CONDITIONS
from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_CONDITION,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_TARGET,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import async_validate_condition_config

_ALL_BUTTON_EVENT_TYPES = [
    "press_start",
    "press_end",
    "long_press_start",
    "long_press_end",
    "single_press",
    "multi_press",
]
_EVENT_ENTITY_ID = "event.test_button"
# Tests of held buttons freeze time here, as a hold times out after the event.
_EVENT_TIMESTAMP = "2026-01-01T00:00:00.000+00:00"


def _button_event(
    event_type: str, event_types: list[str] | None = None
) -> tuple[str, dict[str, Any]]:
    """Build an event entity state, optionally with its declared event types."""
    attributes: dict[str, Any] = {ATTR_EVENT_TYPE: event_type}
    if event_types is not None:
        attributes[ATTR_EVENT_TYPES] = event_types
    return (_EVENT_TIMESTAMP, attributes)


@pytest.fixture
async def target_events(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple event entities associated with different targets."""
    return await target_entities(hass, "event")


_CONDITION_TARGET_SUPPORT: dict[str, TargetSupport] = {
    "is_being_held": TargetSupport.STANDARD,
}


@pytest.mark.parametrize(
    ("condition_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("button.is_being_held", {}, True, True),
    ],
)
async def test_button_condition_options_validation(
    hass: HomeAssistant,
    condition_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that button conditions support the expected options."""
    await assert_condition_options_supported(
        hass,
        condition_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.parametrize(
    "duration",
    [{"seconds": -1}, {"seconds": 30}, "00:01:00", "not_a_duration", None],
)
async def test_button_is_being_held_condition_for_invalid(
    hass: HomeAssistant, duration: dict[str, int] | str | None
) -> None:
    """Test the is_being_held condition rejects a duration that could never pass."""
    with pytest.raises(probatio.Invalid):
        await async_validate_condition_config(
            hass,
            {
                CONF_CONDITION: "button.is_being_held",
                CONF_TARGET: {CONF_ENTITY_ID: _EVENT_ENTITY_ID},
                CONF_OPTIONS: {"for": duration},
            },
        )


def test_condition_target_support() -> None:
    """Certify the condition registry matches its declared target support."""
    assert_conditions_target_support(CONDITIONS, _CONDITION_TARGET_SUPPORT)


# The event types are part of the filter attributes, so unavailable and unknown
# entities still declare them, as real event entities do.
_IS_BEING_HELD_STATES: dict[str, Any] = {
    "condition": "button.is_being_held",
    "target_states": [_button_event("long_press_start")],
    "other_states": [
        _button_event(event_type)
        for event_type in _ALL_BUTTON_EVENT_TYPES
        if event_type != "long_press_start"
    ],
    "required_filter_attributes": {
        ATTR_DEVICE_CLASS: "button",
        ATTR_EVENT_TYPES: _ALL_BUTTON_EVENT_TYPES,
    },
}
# The event types vary per state, to test which entities are skipped.
_IS_BEING_HELD_EVENT_TYPES_STATES: dict[str, Any] = {
    "condition": "button.is_being_held",
    "target_states": [_button_event("long_press_start", _ALL_BUTTON_EVENT_TYPES)],
    "other_states": [
        # Integration-specific event types also end the hold.
        _button_event("custom_event", [*_ALL_BUTTON_EVENT_TYPES, "custom_event"]),
    ],
    "extra_excluded_states": [
        # Entities that don't declare both hold event types are skipped.
        _button_event("long_press_start", ["press_start", "long_press_start"]),
        _button_event("long_press_start", ["long_press_start"]),
        _button_event("long_press_start", ["long_press_end"]),
        _button_event("long_press_start", []),
        _button_event("long_press_start"),
    ],
    "required_filter_attributes": {ATTR_DEVICE_CLASS: "button"},
}


@pytest.mark.freeze_time(_EVENT_TIMESTAMP)
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("event"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(**_IS_BEING_HELD_STATES),
        *parametrize_condition_states_any(**_IS_BEING_HELD_EVENT_TYPES_STATES),
    ],
)
async def test_button_condition_behavior_any(
    hass: HomeAssistant,
    target_events: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the button conditions with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_events,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.freeze_time(_EVENT_TIMESTAMP)
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("event"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(**_IS_BEING_HELD_STATES),
        *parametrize_condition_states_all(**_IS_BEING_HELD_EVENT_TYPES_STATES),
    ],
)
async def test_button_condition_behavior_all(
    hass: HomeAssistant,
    target_events: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the button conditions with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_events,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.freeze_time(_EVENT_TIMESTAMP)
@pytest.mark.parametrize("entity_id", ["button.test_button", "input_button.test"])
async def test_button_is_being_held_condition_ignores_buttons(
    hass: HomeAssistant, entity_id: str
) -> None:
    """Test the is_being_held condition ignores button and input_button entities."""
    # Attributes of a held button, so only the domain filter can keep it out.
    state, attributes = _button_event("long_press_start", _ALL_BUTTON_EVENT_TYPES)
    hass.states.async_set(entity_id, state, attributes | {ATTR_DEVICE_CLASS: "button"})
    await hass.async_block_till_done()

    cond = await create_target_condition(
        hass,
        condition="button.is_being_held",
        target={CONF_ENTITY_ID: entity_id},
        behavior="any",
    )

    assert cond.async_check() is False


@pytest.mark.freeze_time(_EVENT_TIMESTAMP)
async def test_button_is_being_held_condition_for(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the is_being_held condition duration counts from the hold start."""
    attributes = {
        ATTR_DEVICE_CLASS: "button",
        ATTR_EVENT_TYPES: _ALL_BUTTON_EVENT_TYPES,
    }

    def set_event(timestamp: str, event_type: str) -> None:
        hass.states.async_set(
            _EVENT_ENTITY_ID, timestamp, attributes | {ATTR_EVENT_TYPE: event_type}
        )

    set_event("2026-01-01T00:00:00.000+00:00", "long_press_start")
    await hass.async_block_till_done()

    cond = await create_target_condition(
        hass,
        condition="button.is_being_held",
        target={CONF_ENTITY_ID: _EVENT_ENTITY_ID},
        behavior="any",
        condition_options={"for": {"seconds": 5}},
    )
    assert cond.async_check() is False

    freezer.tick(timedelta(seconds=4))
    assert cond.async_check() is False

    freezer.tick(timedelta(seconds=1))
    assert cond.async_check() is True

    # A new hold, after a missed release, restarts the duration.
    set_event("2026-01-01T00:00:05.000+00:00", "long_press_start")
    await hass.async_block_till_done()
    assert cond.async_check() is False

    freezer.tick(timedelta(seconds=5))
    assert cond.async_check() is True

    # The release ends the hold.
    set_event("2026-01-01T00:00:10.000+00:00", "long_press_end")
    await hass.async_block_till_done()
    assert cond.async_check() is False

    freezer.tick(timedelta(seconds=5))
    assert cond.async_check() is False


@pytest.mark.freeze_time(_EVENT_TIMESTAMP)
@pytest.mark.parametrize(
    ("condition_options", "valid_at_hold_start"),
    [
        pytest.param({}, True, id="no_duration"),
        pytest.param({"for": {"seconds": 5}}, False, id="duration"),
    ],
)
async def test_button_is_being_held_condition_timeout(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    condition_options: dict[str, Any],
    valid_at_hold_start: bool,
) -> None:
    """Test the is_being_held condition stops passing when the hold times out."""
    state, attributes = _button_event("long_press_start", _ALL_BUTTON_EVENT_TYPES)
    hass.states.async_set(
        _EVENT_ENTITY_ID, state, attributes | {ATTR_DEVICE_CLASS: "button"}
    )
    await hass.async_block_till_done()

    cond = await create_target_condition(
        hass,
        condition="button.is_being_held",
        target={CONF_ENTITY_ID: _EVENT_ENTITY_ID},
        behavior="any",
        condition_options=condition_options,
    )
    # The timeout changes the result without a state change.
    assert cond.needs_polling is True
    assert cond.async_check() is valid_at_hold_start

    freezer.tick(timedelta(seconds=29.999))
    assert cond.async_check() is True

    # Without a release, the hold ends after the timeout, like the held trigger.
    freezer.tick(timedelta(seconds=0.001))
    assert cond.async_check() is False


@pytest.mark.freeze_time(_EVENT_TIMESTAMP)
@pytest.mark.parametrize(
    ("written_after_event", "times_out_after"),
    [
        # Restored, or available again, with an event from before.
        pytest.param(timedelta(seconds=10), timedelta(seconds=20), id="restored"),
        # The clock went back after the event, so the event is in the future.
        pytest.param(
            timedelta(seconds=-10), timedelta(seconds=30), id="clock_went_back"
        ),
    ],
)
async def test_button_is_being_held_condition_timeout_start(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    written_after_event: timedelta,
    times_out_after: timedelta,
) -> None:
    """Test the hold times out from the earlier of the event and the state change."""
    state, attributes = _button_event("long_press_start", _ALL_BUTTON_EVENT_TYPES)
    freezer.tick(written_after_event)
    hass.states.async_set(
        _EVENT_ENTITY_ID, state, attributes | {ATTR_DEVICE_CLASS: "button"}
    )
    await hass.async_block_till_done()

    cond = await create_target_condition(
        hass,
        condition="button.is_being_held",
        target={CONF_ENTITY_ID: _EVENT_ENTITY_ID},
        behavior="any",
    )
    assert cond.async_check() is True

    freezer.tick(times_out_after - timedelta(milliseconds=1))
    assert cond.async_check() is True

    freezer.tick(timedelta(milliseconds=1))
    assert cond.async_check() is False
