"""Test device tracker conditions."""

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
from homeassistant.helpers.condition import async_validate_condition_config

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)

STATE_WORK_ZONE = "work"


def _gps_state(state: str, in_zones: list[str]) -> tuple[str, dict[str, list[str]]]:
    """Create a GPS-based device tracker state with in_zones attribute."""
    return (state, {ATTR_IN_ZONES: in_zones})


@pytest.fixture
async def target_device_trackers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple device tracker entities associated with different targets."""
    return await target_entities(hass, "device_tracker")


@pytest.mark.parametrize(
    "condition",
    [
        "device_tracker.in_zone",
        "device_tracker.is_home",
        "device_tracker.is_not_home",
        "device_tracker.not_in_zone",
    ],
)
async def test_device_tracker_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the device tracker conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("device_tracker"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="device_tracker.is_home",
            target_states=[STATE_HOME],
            other_states=[STATE_NOT_HOME],
        ),
        *parametrize_condition_states_any(
            condition="device_tracker.is_not_home",
            target_states=[STATE_NOT_HOME],
            other_states=[STATE_HOME],
        ),
    ],
)
async def test_device_tracker_state_condition_behavior_any(
    hass: HomeAssistant,
    target_device_trackers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the device tracker state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_device_trackers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("device_tracker"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="device_tracker.is_home",
            target_states=[STATE_HOME],
            other_states=[STATE_NOT_HOME],
        ),
        *parametrize_condition_states_all(
            condition="device_tracker.is_not_home",
            target_states=[STATE_NOT_HOME],
            other_states=[STATE_HOME],
        ),
    ],
)
async def test_device_tracker_state_condition_behavior_all(
    hass: HomeAssistant,
    target_device_trackers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the device tracker state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_device_trackers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


# Zone conditions for GPS-based trackers (have in_zones attribute)
GPS_ZONE_CONDITIONS_ANY = [
    *parametrize_condition_states_any(
        condition="device_tracker.in_zone",
        condition_options={CONF_ZONE: ["zone.home", "zone.work"]},
        target_states=[
            _gps_state(STATE_HOME, ["zone.home"]),
            _gps_state(STATE_WORK_ZONE, ["zone.work"]),
            _gps_state(STATE_HOME, ["zone.home", "zone.work"]),
        ],
        other_states=[
            _gps_state(STATE_NOT_HOME, []),
            _gps_state("school", ["zone.school"]),
        ],
    ),
    *parametrize_condition_states_any(
        condition="device_tracker.not_in_zone",
        condition_options={CONF_ZONE: ["zone.home", "zone.work"]},
        target_states=[
            _gps_state(STATE_NOT_HOME, []),
            _gps_state("school", ["zone.school"]),
        ],
        other_states=[
            _gps_state(STATE_HOME, ["zone.home"]),
            _gps_state(STATE_WORK_ZONE, ["zone.work"]),
            _gps_state(STATE_HOME, ["zone.home", "zone.work"]),
        ],
    ),
]

GPS_ZONE_CONDITIONS_ALL = [
    *parametrize_condition_states_all(
        condition="device_tracker.in_zone",
        condition_options={CONF_ZONE: ["zone.home", "zone.work"]},
        target_states=[
            _gps_state(STATE_HOME, ["zone.home"]),
            _gps_state(STATE_WORK_ZONE, ["zone.work"]),
            _gps_state(STATE_HOME, ["zone.home", "zone.work"]),
        ],
        other_states=[
            _gps_state(STATE_NOT_HOME, []),
            _gps_state("school", ["zone.school"]),
        ],
    ),
    *parametrize_condition_states_all(
        condition="device_tracker.not_in_zone",
        condition_options={CONF_ZONE: ["zone.home", "zone.work"]},
        target_states=[
            _gps_state(STATE_NOT_HOME, []),
            _gps_state("school", ["zone.school"]),
        ],
        other_states=[
            _gps_state(STATE_HOME, ["zone.home"]),
            _gps_state(STATE_WORK_ZONE, ["zone.work"]),
            _gps_state(STATE_HOME, ["zone.home", "zone.work"]),
        ],
    ),
]

# Zone conditions for scanner-based trackers (no in_zones attribute)
SCANNER_ZONE_CONDITIONS_ANY = [
    *parametrize_condition_states_any(
        condition="device_tracker.in_zone",
        condition_options={CONF_ZONE: ["zone.home"]},
        target_states=[STATE_HOME],
        other_states=[STATE_NOT_HOME],
    ),
    *parametrize_condition_states_any(
        condition="device_tracker.not_in_zone",
        condition_options={CONF_ZONE: ["zone.home"]},
        target_states=[STATE_NOT_HOME],
        other_states=[STATE_HOME],
    ),
]

SCANNER_ZONE_CONDITIONS_ALL = [
    *parametrize_condition_states_all(
        condition="device_tracker.in_zone",
        condition_options={CONF_ZONE: ["zone.home"]},
        target_states=[STATE_HOME],
        other_states=[STATE_NOT_HOME],
    ),
    *parametrize_condition_states_all(
        condition="device_tracker.not_in_zone",
        condition_options={CONF_ZONE: ["zone.home"]},
        target_states=[STATE_NOT_HOME],
        other_states=[STATE_HOME],
    ),
]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "expected_result"),
    [
        # Valid configurations
        (
            "device_tracker.in_zone",
            {CONF_ZONE: ["zone.home", "zone.work"]},
            does_not_raise(),
        ),
        (
            "device_tracker.in_zone",
            {CONF_ZONE: "zone.home"},
            does_not_raise(),
        ),
        (
            "device_tracker.not_in_zone",
            {CONF_ZONE: ["zone.home"]},
            does_not_raise(),
        ),
        # Invalid configurations
        (
            "device_tracker.in_zone",
            {CONF_ZONE: []},
            pytest.raises(vol.Invalid),
        ),
        (
            "device_tracker.in_zone",
            {},
            pytest.raises(vol.Invalid),
        ),
        (
            "device_tracker.in_zone",
            {CONF_ZONE: ["light.living_room"]},
            pytest.raises(vol.Invalid),
        ),
    ],
)
async def test_device_tracker_zone_condition_validation(
    hass: HomeAssistant,
    trigger: str,
    trigger_options: dict[str, Any],
    expected_result: AbstractContextManager,
) -> None:
    """Test device_tracker zone condition config validation."""
    with expected_result:
        await async_validate_condition_config(
            hass,
            {
                "condition": trigger,
                CONF_TARGET: {CONF_ENTITY_ID: "device_tracker.test"},
                CONF_OPTIONS: trigger_options,
            },
        )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("device_tracker"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [*GPS_ZONE_CONDITIONS_ANY, *SCANNER_ZONE_CONDITIONS_ANY],
)
async def test_device_tracker_zone_condition_behavior_any(
    hass: HomeAssistant,
    target_device_trackers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the device tracker zone condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_device_trackers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("device_tracker"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [*GPS_ZONE_CONDITIONS_ALL, *SCANNER_ZONE_CONDITIONS_ALL],
)
async def test_device_tracker_zone_condition_behavior_all(
    hass: HomeAssistant,
    target_device_trackers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the device tracker zone condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_device_trackers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
