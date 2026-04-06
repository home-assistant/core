"""Test schedule triggers."""

from collections.abc import Callable, Coroutine
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.schedule.const import (
    ATTR_NEXT_EVENT,
    CONF_FROM,
    CONF_SUNDAY,
    CONF_TO,
    DOMAIN,
)
from homeassistant.const import CONF_ICON, CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed
from tests.components.common import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)


@pytest.fixture
async def target_schedules(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple schedule entities associated with different targets."""
    return await target_entities(hass, DOMAIN)


@pytest.mark.parametrize(
    "trigger_key",
    [
        "schedule.turned_off",
        "schedule.turned_on",
    ],
)
async def test_schedule_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the schedule triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="schedule.turned_off",
            target_states=[(STATE_OFF, {ATTR_NEXT_EVENT: "2022-08-30T13:20:00-07:00"})],
            other_states=[(STATE_ON, {ATTR_NEXT_EVENT: "2022-08-30T13:30:00-07:00"})],
        ),
        *parametrize_trigger_states(
            trigger="schedule.turned_on",
            target_states=[(STATE_ON, {ATTR_NEXT_EVENT: "2022-08-30T13:20:00-07:00"})],
            other_states=[(STATE_OFF, {ATTR_NEXT_EVENT: "2022-08-30T13:30:00-07:00"})],
        ),
    ],
)
async def test_schedule_state_trigger_behavior_any(
    hass: HomeAssistant,
    target_schedules: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the schedule state trigger fires when any schedule state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_schedules,
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
            trigger="schedule.turned_off",
            target_states=[(STATE_OFF, {ATTR_NEXT_EVENT: "2022-08-30T13:20:00-07:00"})],
            other_states=[(STATE_ON, {ATTR_NEXT_EVENT: "2022-08-30T13:30:00-07:00"})],
        ),
        *parametrize_trigger_states(
            trigger="schedule.turned_on",
            target_states=[(STATE_ON, {ATTR_NEXT_EVENT: "2022-08-30T13:20:00-07:00"})],
            other_states=[(STATE_OFF, {ATTR_NEXT_EVENT: "2022-08-30T13:30:00-07:00"})],
        ),
    ],
)
async def test_schedule_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_schedules: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the schedule state trigger fires when the first schedule changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_schedules,
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
            trigger="schedule.turned_off",
            target_states=[(STATE_OFF, {ATTR_NEXT_EVENT: "2022-08-30T13:20:00-07:00"})],
            other_states=[(STATE_ON, {ATTR_NEXT_EVENT: "2022-08-30T13:30:00-07:00"})],
        ),
        *parametrize_trigger_states(
            trigger="schedule.turned_on",
            target_states=[(STATE_ON, {ATTR_NEXT_EVENT: "2022-08-30T13:20:00-07:00"})],
            other_states=[(STATE_OFF, {ATTR_NEXT_EVENT: "2022-08-30T13:30:00-07:00"})],
        ),
    ],
)
async def test_schedule_state_trigger_behavior_last(
    hass: HomeAssistant,
    target_schedules: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the schedule state trigger fires when the last schedule changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_schedules,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_schedule_state_trigger_back_to_back(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the schedule state trigger fires when transitioning between two back-to-back schedule blocks."""
    calls: list[str] = []
    freezer.move_to("2022-08-30 13:20:00-07:00")
    entity_id = "schedule.from_yaml"

    assert await schedule_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    CONF_NAME: "from yaml",
                    CONF_ICON: "mdi:party-popper",
                    CONF_SUNDAY: [
                        {CONF_FROM: "22:00:00", CONF_TO: "22:30:00"},
                        {CONF_FROM: "22:30:00", CONF_TO: "23:00:00"},
                    ],
                }
            }
        },
        items=[],
    )

    await arm_trigger(
        hass,
        "schedule.turned_on",
        {},
        {"entity_id": [entity_id]},
        calls,
    )

    # initial state
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T22:00:00-07:00"

    # move time into first block
    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T22:30:00-07:00"

    assert len(calls) == 1
    assert calls[0] == entity_id
    calls.clear()

    # move time into second block (back-to-back)
    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T23:00:00-07:00"

    assert len(calls) == 1
    assert calls[0] == entity_id
    calls.clear()

    # move time to after second block to ensure it turns off
    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-11T22:00:00-07:00"

    assert len(calls) == 0
