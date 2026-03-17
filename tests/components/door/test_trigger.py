"""Test door trigger."""

from typing import Any

import pytest

from homeassistant.components.cover import ATTR_IS_CLOSED, CoverState
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall

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
async def target_binary_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple binary sensor entities associated with different targets."""
    return await target_entities(hass, "binary_sensor")


@pytest.fixture
async def target_covers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple cover entities associated with different targets."""
    return await target_entities(hass, "cover")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "door.opened",
        "door.closed",
    ],
)
async def test_door_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the door triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="door.opened",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="door.closed",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
    ],
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
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_binary_sensors,
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
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="door.opened",
            target_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="door.closed",
            target_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
    ],
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
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_covers,
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
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="door.opened",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="door.closed",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
    ],
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
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
        target_entities=target_binary_sensors,
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
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="door.opened",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="door.closed",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
    ],
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
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
        target_entities=target_binary_sensors,
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
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="door.opened",
            target_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="door.closed",
            target_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
    ],
)
async def test_door_trigger_cover_behavior_first(
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
    """Test door trigger fires on the first cover state change."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
        target_entities=target_covers,
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
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="door.opened",
            target_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="door.closed",
            target_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "door"},
            trigger_from_none=False,
        ),
    ],
)
async def test_door_trigger_cover_behavior_last(
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
    """Test door trigger fires when the last cover changes state."""
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
        target_entities=target_covers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    (
        "trigger_key",
        "binary_sensor_initial",
        "binary_sensor_target",
        "cover_initial",
        "cover_initial_is_closed",
        "cover_target",
        "cover_target_is_closed",
    ),
    [
        (
            "door.opened",
            STATE_OFF,
            STATE_ON,
            CoverState.CLOSED,
            True,
            CoverState.OPEN,
            False,
        ),
        (
            "door.closed",
            STATE_ON,
            STATE_OFF,
            CoverState.OPEN,
            False,
            CoverState.CLOSED,
            True,
        ),
    ],
)
async def test_door_trigger_excludes_non_door_device_class(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    binary_sensor_initial: str,
    binary_sensor_target: str,
    cover_initial: str,
    cover_initial_is_closed: bool,
    cover_target: str,
    cover_target_is_closed: bool,
) -> None:
    """Test door trigger does not fire for entities without device_class door."""
    entity_id_door = "binary_sensor.test_door"
    entity_id_window = "binary_sensor.test_window"
    entity_id_cover_door = "cover.test_door"
    entity_id_cover_garage = "cover.test_garage"

    # Set initial states
    hass.states.async_set(
        entity_id_door, binary_sensor_initial, {ATTR_DEVICE_CLASS: "door"}
    )
    hass.states.async_set(
        entity_id_window, binary_sensor_initial, {ATTR_DEVICE_CLASS: "window"}
    )
    hass.states.async_set(
        entity_id_cover_door,
        cover_initial,
        {ATTR_DEVICE_CLASS: "door", ATTR_IS_CLOSED: cover_initial_is_closed},
    )
    hass.states.async_set(
        entity_id_cover_garage,
        cover_initial,
        {ATTR_DEVICE_CLASS: "garage", ATTR_IS_CLOSED: cover_initial_is_closed},
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger_key,
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

    # Door binary_sensor changes - should trigger
    hass.states.async_set(
        entity_id_door, binary_sensor_target, {ATTR_DEVICE_CLASS: "door"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_door
    service_calls.clear()

    # Window binary_sensor changes - should NOT trigger (wrong device class)
    hass.states.async_set(
        entity_id_window, binary_sensor_target, {ATTR_DEVICE_CLASS: "window"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Cover door changes - should trigger
    hass.states.async_set(
        entity_id_cover_door,
        cover_target,
        {ATTR_DEVICE_CLASS: "door", ATTR_IS_CLOSED: cover_target_is_closed},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_cover_door
    service_calls.clear()

    # Garage cover changes - should NOT trigger (wrong device class)
    hass.states.async_set(
        entity_id_cover_garage,
        cover_target,
        {ATTR_DEVICE_CLASS: "garage", ATTR_IS_CLOSED: cover_target_is_closed},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0
