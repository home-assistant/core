"""Test cover triggers."""

from typing import Any

import pytest

from homeassistant.components.cover import ATTR_IS_CLOSED, CoverDeviceClass, CoverState
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant

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

DEVICE_CLASS_TRIGGERS = [
    (CoverDeviceClass.AWNING, "cover.awning_opened", "cover.awning_closed"),
    (CoverDeviceClass.BLIND, "cover.blind_opened", "cover.blind_closed"),
    (CoverDeviceClass.CURTAIN, "cover.curtain_opened", "cover.curtain_closed"),
    (CoverDeviceClass.SHADE, "cover.shade_opened", "cover.shade_closed"),
    (CoverDeviceClass.SHUTTER, "cover.shutter_opened", "cover.shutter_closed"),
]


@pytest.fixture
async def target_covers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple cover entities associated with different targets."""
    return await target_entities(hass, "cover")


@pytest.mark.parametrize(
    "trigger_key",
    [
        trigger
        for _, opened, closed in DEVICE_CLASS_TRIGGERS
        for trigger in (opened, closed)
    ],
)
async def test_cover_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the cover triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        param
        for device_class, opened_key, closed_key in DEVICE_CLASS_TRIGGERS
        for param in (
            *parametrize_trigger_states(
                trigger=opened_key,
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
                required_filter_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
            *parametrize_trigger_states(
                trigger=closed_key,
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
                required_filter_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
        )
    ],
)
async def test_cover_trigger_behavior_any(
    hass: HomeAssistant,
    target_covers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test cover trigger fires for cover entities with matching device_class."""
    await assert_trigger_behavior_any(
        hass,
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
        param
        for device_class, opened_key, closed_key in DEVICE_CLASS_TRIGGERS
        for param in (
            *parametrize_trigger_states(
                trigger=opened_key,
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
                required_filter_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
            *parametrize_trigger_states(
                trigger=closed_key,
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
                required_filter_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
        )
    ],
)
async def test_cover_trigger_behavior_first(
    hass: HomeAssistant,
    target_covers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test cover trigger fires on the first cover state change."""
    await assert_trigger_behavior_first(
        hass,
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
        param
        for device_class, opened_key, closed_key in DEVICE_CLASS_TRIGGERS
        for param in (
            *parametrize_trigger_states(
                trigger=opened_key,
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
                required_filter_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
            *parametrize_trigger_states(
                trigger=closed_key,
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
                required_filter_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
        )
    ],
)
async def test_cover_trigger_behavior_last(
    hass: HomeAssistant,
    target_covers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test cover trigger fires when the last cover changes state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_covers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
