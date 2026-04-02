"""Test device_tracker trigger."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.device_tracker.const import ATTR_IN_ZONES
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_TARGET,
    CONF_ZONE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import async_validate_trigger_config

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

STATE_WORK_ZONE = "work"


def _dt_state(state: str, in_zones: list[str]) -> tuple[str, dict[str, list[str]]]:
    """Create a device tracker state tuple with in_zones attribute."""
    return (state, {ATTR_IN_ZONES: in_zones})


ZONE_TRIGGERS = [
    *parametrize_trigger_states(
        trigger="device_tracker.entered_zone",
        trigger_options={CONF_ZONE: ["zone.home", "zone.work"]},
        target_states=[
            # In zone.home
            _dt_state(STATE_HOME, ["zone.home"]),
            # In zone.work
            _dt_state(STATE_WORK_ZONE, ["zone.work"]),
            # In both zones
            _dt_state(STATE_HOME, ["zone.home", "zone.work"]),
        ],
        other_states=[
            # Not in any selected zone
            _dt_state(STATE_NOT_HOME, []),
            # In an unrelated zone
            _dt_state("school", ["zone.school"]),
        ],
    ),
    *parametrize_trigger_states(
        trigger="device_tracker.left_zone",
        trigger_options={CONF_ZONE: ["zone.home", "zone.work"]},
        target_states=[
            # Not in any selected zone
            _dt_state(STATE_NOT_HOME, []),
            # In an unrelated zone only
            _dt_state("school", ["zone.school"]),
        ],
        other_states=[
            # In zone.home
            _dt_state(STATE_HOME, ["zone.home"]),
            # In zone.work
            _dt_state(STATE_WORK_ZONE, ["zone.work"]),
            # In both zones
            _dt_state(STATE_HOME, ["zone.home", "zone.work"]),
        ],
    ),
]


@pytest.fixture
async def target_device_trackers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple device_trackers entities associated with different targets."""
    return await target_entities(hass, "device_tracker")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "device_tracker.entered_home",
        "device_tracker.entered_zone",
        "device_tracker.left_home",
        "device_tracker.left_zone",
    ],
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
    target_device_trackers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the device_tracker home triggers when the last device_tracker changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
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
    ("trigger", "trigger_options", "expected_result"),
    [
        # Valid configurations
        (
            "device_tracker.entered_zone",
            {CONF_ZONE: ["zone.home", "zone.work"]},
            does_not_raise(),
        ),
        (
            "device_tracker.entered_zone",
            {CONF_ZONE: "zone.home"},
            does_not_raise(),
        ),
        (
            "device_tracker.left_zone",
            {CONF_ZONE: ["zone.home"]},
            does_not_raise(),
        ),
        # Invalid configurations
        (
            "device_tracker.entered_zone",
            {CONF_ZONE: []},
            pytest.raises(vol.Invalid),
        ),
        (
            "device_tracker.entered_zone",
            {},
            pytest.raises(vol.Invalid),
        ),
        (
            "device_tracker.entered_zone",
            # Not a zone entity
            {CONF_ZONE: ["light.living_room"]},
            pytest.raises(vol.Invalid),
        ),
    ],
)
async def test_device_tracker_zone_trigger_validation(
    hass: HomeAssistant,
    trigger: str,
    trigger_options: dict[str, Any],
    expected_result: AbstractContextManager,
) -> None:
    """Test device_tracker zone trigger config validation."""
    with expected_result:
        await async_validate_trigger_config(
            hass,
            [
                {
                    "platform": trigger,
                    CONF_TARGET: {CONF_ENTITY_ID: "device_tracker.test"},
                    CONF_OPTIONS: trigger_options,
                }
            ],
        )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("device_tracker"),
)
@pytest.mark.parametrize(("trigger", "trigger_options", "states"), ZONE_TRIGGERS)
async def test_device_tracker_zone_trigger_behavior_any(
    hass: HomeAssistant,
    target_device_trackers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the zone triggers fire when any device_tracker enters/leaves a zone."""
    await assert_trigger_behavior_any(
        hass,
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
@pytest.mark.parametrize(("trigger", "trigger_options", "states"), ZONE_TRIGGERS)
async def test_device_tracker_zone_trigger_behavior_first(
    hass: HomeAssistant,
    target_device_trackers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the zone triggers fire when the first device_tracker enters/leaves a zone."""
    await assert_trigger_behavior_first(
        hass,
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
@pytest.mark.parametrize(("trigger", "trigger_options", "states"), ZONE_TRIGGERS)
async def test_device_tracker_zone_trigger_behavior_last(
    hass: HomeAssistant,
    target_device_trackers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the zone triggers fire when the last device_tracker enters/leaves a zone."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_device_trackers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
