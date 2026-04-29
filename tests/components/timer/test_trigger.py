"""Test timer triggers."""

from typing import Any

import pytest

from homeassistant.components.timer import (
    ATTR_LAST_TRANSITION,
    DOMAIN,
    STATUS_ACTIVE,
    STATUS_IDLE,
    STATUS_PAUSED,
)
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    assert_trigger_options_supported,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)


@pytest.fixture
async def target_timers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple timer entities associated with different targets."""
    return await target_entities(hass, DOMAIN)


@pytest.mark.parametrize(
    "trigger_key",
    [
        "timer.cancelled",
        "timer.finished",
        "timer.paused",
        "timer.restarted",
        "timer.started",
    ],
)
async def test_timer_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the timer triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("timer.cancelled", {}, True, True),
        ("timer.finished", {}, True, True),
        ("timer.paused", {}, True, True),
        ("timer.restarted", {}, True, True),
        ("timer.started", {}, True, True),
    ],
)
async def test_timer_trigger_options_validation(
    hass: HomeAssistant,
    trigger_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that timer triggers support the expected options."""
    await assert_trigger_options_supported(
        hass,
        trigger_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="timer.cancelled",
            target_states=[(STATUS_IDLE, {ATTR_LAST_TRANSITION: "cancelled"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.finished",
            target_states=[(STATUS_IDLE, {ATTR_LAST_TRANSITION: "finished"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.paused",
            target_states=[(STATUS_PAUSED, {ATTR_LAST_TRANSITION: "paused"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.restarted",
            target_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "restarted"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.started",
            target_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
            other_states=[(STATUS_IDLE, {ATTR_LAST_TRANSITION: "cancelled"})],
        ),
    ],
)
async def test_timer_trigger_behavior_any(
    hass: HomeAssistant,
    target_timers: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the timer trigger fires when any timer's last_transition changes to a specific value."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_timers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="timer.cancelled",
            target_states=[(STATUS_IDLE, {ATTR_LAST_TRANSITION: "cancelled"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.finished",
            target_states=[(STATUS_IDLE, {ATTR_LAST_TRANSITION: "finished"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.paused",
            target_states=[(STATUS_PAUSED, {ATTR_LAST_TRANSITION: "paused"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.restarted",
            target_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "restarted"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.started",
            target_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
            other_states=[(STATUS_IDLE, {ATTR_LAST_TRANSITION: "cancelled"})],
        ),
    ],
)
async def test_timer_trigger_behavior_first(
    hass: HomeAssistant,
    target_timers: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the timer trigger fires when the first timer's last_transition changes to a specific value."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_timers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="timer.cancelled",
            target_states=[(STATUS_IDLE, {ATTR_LAST_TRANSITION: "cancelled"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.finished",
            target_states=[(STATUS_IDLE, {ATTR_LAST_TRANSITION: "finished"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.paused",
            target_states=[(STATUS_PAUSED, {ATTR_LAST_TRANSITION: "paused"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.restarted",
            target_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "restarted"})],
            other_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
        ),
        *parametrize_trigger_states(
            trigger="timer.started",
            target_states=[(STATUS_ACTIVE, {ATTR_LAST_TRANSITION: "started"})],
            other_states=[(STATUS_IDLE, {ATTR_LAST_TRANSITION: "cancelled"})],
        ),
    ],
)
async def test_timer_trigger_behavior_last(
    hass: HomeAssistant,
    target_timers: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the timer trigger fires when the last timer's last_transition changes to a specific value."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_timers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
