"""Test device_tracker trigger."""

from typing import Any

import pytest

from homeassistant.const import (
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components import (
    TriggerStateDescription,
    arm_trigger,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)

STATE_WORK_ZONE = "work"


@pytest.fixture
async def target_device_trackers(hass: HomeAssistant) -> list[str]:
    """Create multiple device_trackers entities associated with different targets."""
    return (await target_entities(hass, "device_tracker"))["included"]


@pytest.mark.parametrize(
    "trigger_key",
    ["device_tracker.entered_home", "device_tracker.left_home"],
)
async def test_device_tracker_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the device_tracker triggers are gated by the labs flag."""
    await arm_trigger(hass, trigger_key, None, {ATTR_LABEL_ID: "test_label"})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger_key}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


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
    target_device_trackers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the device_tracker home triggers when any device_tracker changes to a specific state."""
    other_entity_ids = set(target_device_trackers) - {entity_id}

    # Set all device_trackers, including the tested device_tracker, to the initial state
    for eid in target_device_trackers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check that changing other device_trackers also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


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
    target_device_trackers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the device_tracker home triggers when the first device_tracker changes to a specific state."""
    other_entity_ids = set(target_device_trackers) - {entity_id}

    # Set all device_trackers, including the tested device_tracker, to the initial state
    for eid in target_device_trackers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other device_trackers should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


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
    target_device_trackers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the device_tracker home triggers when the last device_tracker changes to a specific state."""
    other_entity_ids = set(target_device_trackers) - {entity_id}

    # Set all device_trackers, including the tested device_tracker, to the initial state
    for eid in target_device_trackers:
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
