"""Test device_tracker trigger."""

from typing import Any

import pytest

from homeassistant.const import CONF_ENTITY_ID, STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components.common import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)

STATE_WORK_ZONE = "work"


@pytest.fixture
async def target_device_trackers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple device_trackers entities associated with different targets."""
    return await target_entities(hass, "device_tracker")


@pytest.mark.parametrize(
    "trigger_key",
    ["device_tracker.entered_home", "device_tracker.left_home"],
)
async def test_device_tracker_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the device_tracker triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("device_tracker"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="device_tracker.entered_home",
            target_states=[STATE_HOME],
            other_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
        ),
        *parametrize_trigger_states(
            trigger="device_tracker.left_home",
            target_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
            other_states=[STATE_HOME],
        ),
    ],
)
async def test_device_tracker_home_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_device_trackers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the device_tracker home triggers when any device_tracker changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_device_trackers,
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
    parametrize_target_entities("device_tracker"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="device_tracker.entered_home",
            target_states=[STATE_HOME],
            other_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
        ),
        *parametrize_trigger_states(
            trigger="device_tracker.left_home",
            target_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
            other_states=[STATE_HOME],
        ),
    ],
)
async def test_device_tracker_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_device_trackers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the device_tracker home triggers when the first device_tracker changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
        target_entities=target_device_trackers,
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
    parametrize_target_entities("device_tracker"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="device_tracker.entered_home",
            target_states=[STATE_HOME],
            other_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
        ),
        *parametrize_trigger_states(
            trigger="device_tracker.left_home",
            target_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
            other_states=[STATE_HOME],
        ),
    ],
)
async def test_device_tracker_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_device_trackers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the device_tracker home triggers when the last device_tracker changes to a specific state."""
    other_entity_ids = set(target_device_trackers["included"]) - {entity_id}

    # Set all device_trackers, including the tested device_tracker, to the initial state
    for eid in target_device_trackers["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
