"""Test door trigger."""

from typing import Any

import pytest

from homeassistant.components.cover import CoverState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
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


@pytest.fixture
async def target_binary_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple binary sensor entities associated with different targets."""
    return await target_entities(hass, "binary_sensor")


@pytest.fixture
async def target_covers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple cover entities associated with different targets."""
    return await target_entities(hass, "cover")


async def test_door_trigger_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the door trigger is gated by the labs flag."""
    await arm_trigger(hass, "door.opened", None, {ATTR_LABEL_ID: "test_label"})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        "'door.opened' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    parametrize_trigger_states(
        trigger="door.opened",
        target_states=[STATE_ON],
        other_states=[STATE_OFF],
        additional_attributes={ATTR_DEVICE_CLASS: "door"},
        trigger_from_none=False,
    ),
)
async def test_door_trigger_binary_sensor_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test door trigger fires for binary_sensor entities with device_class door."""
    other_entity_ids = set(target_binary_sensors["included"]) - {entity_id}
    excluded_entity_ids = set(target_binary_sensors["excluded"]) - {entity_id}

    for eid in target_binary_sensors["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state in states[1:]:
        excluded_state = state["excluded"]
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    parametrize_trigger_states(
        trigger="door.opened",
        target_states=[CoverState.OPEN, CoverState.OPENING],
        other_states=[CoverState.CLOSED, CoverState.CLOSING],
        additional_attributes={ATTR_DEVICE_CLASS: "door"},
        trigger_from_none=False,
    ),
)
async def test_door_trigger_cover_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_covers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test door trigger fires for cover entities with device_class door."""
    other_entity_ids = set(target_covers["included"]) - {entity_id}
    excluded_entity_ids = set(target_covers["excluded"]) - {entity_id}

    for eid in target_covers["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state in states[1:]:
        excluded_state = state["excluded"]
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    parametrize_trigger_states(
        trigger="door.opened",
        target_states=[STATE_ON],
        other_states=[STATE_OFF],
        additional_attributes={ATTR_DEVICE_CLASS: "door"},
        trigger_from_none=False,
    ),
)
async def test_door_trigger_binary_sensor_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test door trigger fires on the first binary_sensor state change."""
    other_entity_ids = set(target_binary_sensors["included"]) - {entity_id}
    excluded_entity_ids = set(target_binary_sensors["excluded"]) - {entity_id}

    for eid in target_binary_sensors["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state in states[1:]:
        excluded_state = state["excluded"]
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, excluded_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    parametrize_trigger_states(
        trigger="door.opened",
        target_states=[STATE_ON],
        other_states=[STATE_OFF],
        additional_attributes={ATTR_DEVICE_CLASS: "door"},
        trigger_from_none=False,
    ),
)
async def test_door_trigger_binary_sensor_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test door trigger fires when the last binary_sensor changes state."""
    other_entity_ids = set(target_binary_sensors["included"]) - {entity_id}
    excluded_entity_ids = set(target_binary_sensors["excluded"]) - {entity_id}

    for eid in target_binary_sensors["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state in states[1:]:
        excluded_state = state["excluded"]
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_door_trigger_excludes_non_door_device_class(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
) -> None:
    """Test door trigger does not fire for entities without device_class door."""
    entity_id_door = "binary_sensor.test_door"
    entity_id_window = "binary_sensor.test_window"
    entity_id_cover_door = "cover.test_door"
    entity_id_cover_garage = "cover.test_garage"

    # Set initial states
    hass.states.async_set(entity_id_door, STATE_OFF, {ATTR_DEVICE_CLASS: "door"})
    hass.states.async_set(entity_id_window, STATE_OFF, {ATTR_DEVICE_CLASS: "window"})
    hass.states.async_set(
        entity_id_cover_door, CoverState.CLOSED, {ATTR_DEVICE_CLASS: "door"}
    )
    hass.states.async_set(
        entity_id_cover_garage,
        CoverState.CLOSED,
        {ATTR_DEVICE_CLASS: "garage"},
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "door.opened",
        {},
        {
            CONF_ENTITY_ID: [
                entity_id_door,
                entity_id_window,
                entity_id_cover_door,
                entity_id_cover_garage,
            ]
        },
    )

    # Door binary_sensor opens - should trigger
    hass.states.async_set(entity_id_door, STATE_ON, {ATTR_DEVICE_CLASS: "door"})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_door
    service_calls.clear()

    # Window binary_sensor opens - should NOT trigger (wrong device class)
    hass.states.async_set(entity_id_window, STATE_ON, {ATTR_DEVICE_CLASS: "window"})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Cover door opens - should trigger
    hass.states.async_set(
        entity_id_cover_door, CoverState.OPEN, {ATTR_DEVICE_CLASS: "door"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_cover_door
    service_calls.clear()

    # Garage cover opens - should NOT trigger (wrong device class)
    hass.states.async_set(
        entity_id_cover_garage,
        CoverState.OPEN,
        {ATTR_DEVICE_CLASS: "garage"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0
