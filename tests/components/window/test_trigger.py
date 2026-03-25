"""Test window trigger."""

from typing import Any

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.cover import ATTR_IS_CLOSED, CoverDeviceClass, CoverState
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components.common import (
    TriggerStateDescription,
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
        "window.opened",
        "window.closed",
    ],
)
async def test_window_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the window triggers are gated by the labs flag."""
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
            trigger="window.opened",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.WINDOW
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="window.closed",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.WINDOW
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_window_trigger_binary_sensor_behavior_any(
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
    """Test window trigger fires for binary_sensor entities with device_class window."""
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
            trigger="window.opened",
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
            required_filter_attributes={ATTR_DEVICE_CLASS: CoverDeviceClass.WINDOW},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="window.closed",
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
            required_filter_attributes={ATTR_DEVICE_CLASS: CoverDeviceClass.WINDOW},
            trigger_from_none=False,
        ),
    ],
)
async def test_window_trigger_cover_behavior_any(
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
    """Test window trigger fires for cover entities with device_class window."""
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
            trigger="window.opened",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.WINDOW
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="window.closed",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.WINDOW
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_window_trigger_binary_sensor_behavior_first(
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
    """Test window trigger fires on the first binary_sensor state change."""
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
            trigger="window.opened",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.WINDOW
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="window.closed",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.WINDOW
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_window_trigger_binary_sensor_behavior_last(
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
    """Test window trigger fires when the last binary_sensor changes state."""
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
            trigger="window.opened",
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
            required_filter_attributes={ATTR_DEVICE_CLASS: CoverDeviceClass.WINDOW},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="window.closed",
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
            required_filter_attributes={ATTR_DEVICE_CLASS: CoverDeviceClass.WINDOW},
            trigger_from_none=False,
        ),
    ],
)
async def test_window_trigger_cover_behavior_first(
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
    """Test window trigger fires on the first cover state change."""
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
            trigger="window.opened",
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
            required_filter_attributes={ATTR_DEVICE_CLASS: CoverDeviceClass.WINDOW},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="window.closed",
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
            required_filter_attributes={ATTR_DEVICE_CLASS: CoverDeviceClass.WINDOW},
            trigger_from_none=False,
        ),
    ],
)
async def test_window_trigger_cover_behavior_last(
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
    """Test window trigger fires when the last cover changes state."""
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
