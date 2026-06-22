"""Test timer triggers."""

from datetime import timedelta
import logging
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant.components.timer import (
    ATTR_FINISHES_AT,
    ATTR_LAST_TRANSITION,
    DOMAIN,
    STATUS_ACTIVE,
    STATUS_IDLE,
    STATUS_PAUSED,
)
from homeassistant.const import (
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TARGET,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, label_registry as lr
from homeassistant.helpers.trigger import (
    async_initialize_triggers,
    async_validate_trigger_config,
)
from homeassistant.helpers.typing import TemplateVarsType
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_all,
    assert_trigger_behavior_each,
    assert_trigger_behavior_first,
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
        "timer.time_remaining",
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
        ("timer.time_remaining", {"remaining": {"hours": 1}}, False, False),
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
async def test_timer_trigger_behavior_each(
    hass: HomeAssistant,
    target_timers: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test timer trigger fires on any timer last_transition change."""
    await assert_trigger_behavior_each(
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
    """Test timer trigger fires on first timer last_transition change."""
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
async def test_timer_trigger_behavior_all(
    hass: HomeAssistant,
    target_timers: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test timer trigger fires when all timers have transitioned."""
    await assert_trigger_behavior_all(
        hass,
        target_entities=target_timers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


# --- time_remaining trigger tests ---


async def _arm_time_remaining_trigger(
    hass: HomeAssistant,
    entity_id: str,
    remaining: dict[str, int],
    calls: list[dict[str, Any]],
    *,
    target: dict[str, Any] | None = None,
) -> None:
    """Arm the time_remaining trigger."""
    trigger_config = await async_validate_trigger_config(
        hass,
        [
            {
                CONF_PLATFORM: "timer.time_remaining",
                CONF_TARGET: target or {CONF_ENTITY_ID: entity_id},
                CONF_OPTIONS: {"remaining": remaining},
            }
        ],
    )

    @callback
    def action(run_variables: TemplateVarsType, context: Context | None = None) -> None:
        calls.append(run_variables["trigger"])

    logger = logging.getLogger(__name__)

    def log_cb(level: int, msg: str, **kwargs: Any) -> None:
        logger._log(level, "%s", msg, **kwargs)

    await async_initialize_triggers(
        hass,
        trigger_config,
        action,
        domain="test",
        name="test_trigger",
        log_cb=log_cb,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_validation(hass: HomeAssistant) -> None:
    """Test time_remaining trigger config validation."""
    # Valid config
    await async_validate_trigger_config(
        hass,
        [
            {
                CONF_PLATFORM: "timer.time_remaining",
                CONF_TARGET: {CONF_ENTITY_ID: "timer.test"},
                CONF_OPTIONS: {"remaining": {"seconds": 30}},
            }
        ],
    )

    # Missing remaining option
    with pytest.raises(vol.Invalid):
        await async_validate_trigger_config(
            hass,
            [
                {
                    CONF_PLATFORM: "timer.time_remaining",
                    CONF_TARGET: {CONF_ENTITY_ID: "timer.test"},
                    CONF_OPTIONS: {},
                }
            ],
        )


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_fires(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test time_remaining trigger fires at the right time."""
    now = dt_util.utcnow()
    calls: list[dict[str, Any]] = []

    hass.states.async_set("timer.test", STATUS_IDLE, {ATTR_LAST_TRANSITION: None})
    await hass.async_block_till_done()

    await _arm_time_remaining_trigger(hass, "timer.test", {"seconds": 30}, calls)

    # Start timer with 60 second duration
    finishes_at = now + timedelta(seconds=60)
    hass.states.async_set(
        "timer.test",
        STATUS_ACTIVE,
        {ATTR_LAST_TRANSITION: "started", ATTR_FINISHES_AT: finishes_at.isoformat()},
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Advance to 25 seconds - 35 seconds remaining, should not fire
    freezer.move_to(now + timedelta(seconds=25))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Advance to 30 seconds - 30 seconds remaining, should fire
    freezer.move_to(now + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0]["entity_id"] == "timer.test"
    assert calls[0]["remaining"] == timedelta(seconds=30)


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_paused_before_threshold(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test time_remaining trigger does not fire when timer is paused."""
    now = dt_util.utcnow()
    calls: list[dict[str, Any]] = []

    hass.states.async_set("timer.test", STATUS_IDLE, {ATTR_LAST_TRANSITION: None})
    await hass.async_block_till_done()

    await _arm_time_remaining_trigger(hass, "timer.test", {"seconds": 30}, calls)

    # Start timer with 60 second duration
    finishes_at = now + timedelta(seconds=60)
    hass.states.async_set(
        "timer.test",
        STATUS_ACTIVE,
        {ATTR_LAST_TRANSITION: "started", ATTR_FINISHES_AT: finishes_at.isoformat()},
    )
    await hass.async_block_till_done()

    # Pause timer at 10 seconds (before the 30-second threshold)
    freezer.move_to(now + timedelta(seconds=10))
    hass.states.async_set(
        "timer.test",
        STATUS_PAUSED,
        {ATTR_LAST_TRANSITION: "paused"},
    )
    await hass.async_block_till_done()

    # Advance past the original fire time - should not fire since paused
    freezer.move_to(now + timedelta(seconds=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_cancelled_before_threshold(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test time_remaining trigger does not fire when timer is cancelled."""
    now = dt_util.utcnow()
    calls: list[dict[str, Any]] = []

    hass.states.async_set("timer.test", STATUS_IDLE, {ATTR_LAST_TRANSITION: None})
    await hass.async_block_till_done()

    await _arm_time_remaining_trigger(hass, "timer.test", {"seconds": 30}, calls)

    # Start timer with 60 second duration
    finishes_at = now + timedelta(seconds=60)
    hass.states.async_set(
        "timer.test",
        STATUS_ACTIVE,
        {ATTR_LAST_TRANSITION: "started", ATTR_FINISHES_AT: finishes_at.isoformat()},
    )
    await hass.async_block_till_done()

    # Cancel timer at 10 seconds
    freezer.move_to(now + timedelta(seconds=10))
    hass.states.async_set(
        "timer.test",
        STATUS_IDLE,
        {ATTR_LAST_TRANSITION: "cancelled"},
    )
    await hass.async_block_till_done()

    # Advance past the original fire time - should not fire since cancelled
    freezer.move_to(now + timedelta(seconds=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_restarted(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test time_remaining trigger reschedules when timer is restarted."""
    now = dt_util.utcnow()
    calls: list[dict[str, Any]] = []

    hass.states.async_set("timer.test", STATUS_IDLE, {ATTR_LAST_TRANSITION: None})
    await hass.async_block_till_done()

    await _arm_time_remaining_trigger(hass, "timer.test", {"seconds": 30}, calls)

    # Start timer with 60 second duration
    finishes_at = now + timedelta(seconds=60)
    hass.states.async_set(
        "timer.test",
        STATUS_ACTIVE,
        {ATTR_LAST_TRANSITION: "started", ATTR_FINISHES_AT: finishes_at.isoformat()},
    )
    await hass.async_block_till_done()

    # Restart timer at 10 seconds with a new 60-second duration
    freezer.move_to(now + timedelta(seconds=10))
    new_finishes_at = now + timedelta(seconds=70)  # 10s elapsed + 60s new
    hass.states.async_set(
        "timer.test",
        STATUS_ACTIVE,
        {
            ATTR_LAST_TRANSITION: "restarted",
            ATTR_FINISHES_AT: new_finishes_at.isoformat(),
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Original fire time (30s) should not fire since rescheduled
    freezer.move_to(now + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 0

    # New fire time: new_finishes_at - 30s = now + 40s
    freezer.move_to(now + timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 1


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_short_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test time_remaining trigger skips when duration < threshold."""
    now = dt_util.utcnow()
    calls: list[dict[str, Any]] = []

    hass.states.async_set("timer.test", STATUS_IDLE, {ATTR_LAST_TRANSITION: None})
    await hass.async_block_till_done()

    await _arm_time_remaining_trigger(hass, "timer.test", {"seconds": 30}, calls)

    # Start timer with only 20 second duration (less than 30s threshold)
    finishes_at = now + timedelta(seconds=20)
    hass.states.async_set(
        "timer.test",
        STATUS_ACTIVE,
        {ATTR_LAST_TRANSITION: "started", ATTR_FINISHES_AT: finishes_at.isoformat()},
    )
    await hass.async_block_till_done()

    # fire_at = now + 20 - 30 = now - 10 (in the past), should not schedule
    # Advance past the timer's end time
    freezer.move_to(now + timedelta(seconds=25))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_already_active_at_attach(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trigger schedules for timers already active when the trigger attaches."""
    now = dt_util.utcnow()
    calls: list[dict[str, Any]] = []

    # Timer is already active before the trigger is armed
    finishes_at = now + timedelta(seconds=60)
    hass.states.async_set(
        "timer.test",
        STATUS_ACTIVE,
        {ATTR_LAST_TRANSITION: "started", ATTR_FINISHES_AT: finishes_at.isoformat()},
    )
    await hass.async_block_till_done()

    await _arm_time_remaining_trigger(hass, "timer.test", {"seconds": 30}, calls)

    # No fire yet
    assert len(calls) == 0

    # Before fire_at (finishes_at - 30s = now + 30s) — should not fire
    freezer.move_to(now + timedelta(seconds=25))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 0

    # At fire_at — should fire even though no state change occurred
    freezer.move_to(now + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0]["entity_id"] == "timer.test"
    assert calls[0]["remaining"] == timedelta(seconds=30)


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_already_active_past_threshold_at_attach(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trigger ignores timers already past the fire point at attach."""
    now = dt_util.utcnow()
    calls: list[dict[str, Any]] = []

    # Timer is active but only 20 seconds remain — past the 30s threshold already
    finishes_at = now + timedelta(seconds=20)
    hass.states.async_set(
        "timer.test",
        STATUS_ACTIVE,
        {ATTR_LAST_TRANSITION: "started", ATTR_FINISHES_AT: finishes_at.isoformat()},
    )
    await hass.async_block_till_done()

    await _arm_time_remaining_trigger(hass, "timer.test", {"seconds": 30}, calls)

    # Advance past the timer's finishing time — should never fire
    freezer.move_to(now + timedelta(seconds=25))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_idle_at_attach(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trigger does not schedule for non-active timers at attach time."""
    now = dt_util.utcnow()
    calls: list[dict[str, Any]] = []

    hass.states.async_set("timer.test", STATUS_IDLE, {ATTR_LAST_TRANSITION: None})
    await hass.async_block_till_done()

    await _arm_time_remaining_trigger(hass, "timer.test", {"seconds": 30}, calls)

    # Even far in the future, no fire because timer never started
    freezer.move_to(now + timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_active_on_first_state_event(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trigger schedules when first observed state event has no from_state.

    This simulates a timer entity that is created/restored after the trigger
    is attached and appears directly in active state (e.g., RestoreEntity on
    restart), where the initial state-change event has from_state=None.
    """
    now = dt_util.utcnow()
    calls: list[dict[str, Any]] = []

    await _arm_time_remaining_trigger(hass, "timer.test", {"seconds": 30}, calls)

    # First state event for the entity has no old_state
    finishes_at = now + timedelta(seconds=60)
    hass.states.async_set(
        "timer.test",
        STATUS_ACTIVE,
        {ATTR_LAST_TRANSITION: "started", ATTR_FINISHES_AT: finishes_at.isoformat()},
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Advance to fire time — should still fire even though from_state was None
    freezer.move_to(now + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0]["entity_id"] == "timer.test"
    assert calls[0]["remaining"] == timedelta(seconds=30)


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_entity_removed_from_target(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test trigger cancels scheduled fire when entity is removed from the target."""
    now = dt_util.utcnow()
    calls: list[dict[str, Any]] = []

    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Test Time Remaining")

    entry = entity_registry.async_get_or_create(
        domain=DOMAIN, platform="test", unique_id="time_remaining_remove"
    )
    entity_registry.async_update_entity(entry.entity_id, labels={label.label_id})

    hass.states.async_set(entry.entity_id, STATUS_IDLE, {ATTR_LAST_TRANSITION: None})
    await hass.async_block_till_done()

    await _arm_time_remaining_trigger(
        hass,
        entry.entity_id,
        {"seconds": 30},
        calls,
        target={ATTR_LABEL_ID: label.label_id},
    )

    # Start the timer — this schedules a fire via the state-change path
    finishes_at = now + timedelta(seconds=60)
    hass.states.async_set(
        entry.entity_id,
        STATUS_ACTIVE,
        {ATTR_LAST_TRANSITION: "started", ATTR_FINISHES_AT: finishes_at.isoformat()},
    )
    await hass.async_block_till_done()

    # Remove the entity from the target by stripping its label
    freezer.move_to(now + timedelta(seconds=10))
    entity_registry.async_update_entity(entry.entity_id, labels=set())
    await hass.async_block_till_done()

    # Advance past the original fire time — should not fire since cancelled
    freezer.move_to(now + timedelta(seconds=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_time_remaining_trigger_entity_added_to_target(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test trigger schedules a fire for an active timer added to the target later."""
    now = dt_util.utcnow()
    calls: list[dict[str, Any]] = []

    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Test Time Remaining Add")

    entry = entity_registry.async_get_or_create(
        domain=DOMAIN, platform="test", unique_id="time_remaining_add"
    )

    # Timer is active, but not in the target yet
    finishes_at = now + timedelta(seconds=60)
    hass.states.async_set(
        entry.entity_id,
        STATUS_ACTIVE,
        {ATTR_LAST_TRANSITION: "started", ATTR_FINISHES_AT: finishes_at.isoformat()},
    )
    await hass.async_block_till_done()

    await _arm_time_remaining_trigger(
        hass,
        entry.entity_id,
        {"seconds": 30},
        calls,
        target={ATTR_LABEL_ID: label.label_id},
    )

    # Now label the entity so it joins the target
    entity_registry.async_update_entity(entry.entity_id, labels={label.label_id})
    await hass.async_block_till_done()

    # Advance to the fire time — should fire even though no state change occurred
    freezer.move_to(now + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0]["entity_id"] == entry.entity_id
    assert calls[0]["remaining"] == timedelta(seconds=30)
