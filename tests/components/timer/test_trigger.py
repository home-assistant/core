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
from homeassistant.const import CONF_ENTITY_ID, CONF_OPTIONS, CONF_PLATFORM, CONF_TARGET
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.trigger import (
    async_initialize_triggers,
    async_validate_trigger_config,
)
from homeassistant.helpers.typing import TemplateVarsType
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
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


# --- time_remaining trigger tests ---


async def _arm_time_remaining_trigger(
    hass: HomeAssistant,
    entity_id: str,
    remaining: dict[str, int],
    calls: list[dict[str, Any]],
) -> None:
    """Arm the time_remaining trigger."""
    trigger_config = await async_validate_trigger_config(
        hass,
        [
            {
                CONF_PLATFORM: "timer.time_remaining",
                CONF_TARGET: {CONF_ENTITY_ID: entity_id},
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
    """Test time_remaining trigger does not fire when timer is paused before threshold."""
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
    """Test time_remaining trigger does not fire when timer is cancelled before threshold."""
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
    """Test time_remaining trigger does not fire when timer duration is shorter than remaining threshold."""
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
