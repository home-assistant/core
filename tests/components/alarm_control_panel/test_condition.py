"""Test alarm_control_panel conditions."""

from typing import Any

import pytest

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    assert_condition_options_supported,
    other_states,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_alarm_control_panels(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple alarm_control_panel entities associated with different targets."""
    return await target_entities(hass, "alarm_control_panel")


@pytest.mark.parametrize(
    "condition",
    [
        "alarm_control_panel.is_armed",
        "alarm_control_panel.is_armed_away",
        "alarm_control_panel.is_armed_home",
        "alarm_control_panel.is_armed_night",
        "alarm_control_panel.is_armed_vacation",
        "alarm_control_panel.is_disarmed",
        "alarm_control_panel.is_triggered",
    ],
)
async def test_alarm_control_panel_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the alarm_control_panel conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("alarm_control_panel.is_armed", {}, True, False),
        ("alarm_control_panel.is_armed_away", {}, True, True),
        ("alarm_control_panel.is_armed_home", {}, True, True),
        ("alarm_control_panel.is_armed_night", {}, True, True),
        ("alarm_control_panel.is_armed_vacation", {}, True, True),
        ("alarm_control_panel.is_disarmed", {}, True, True),
        ("alarm_control_panel.is_triggered", {}, True, True),
    ],
)
async def test_alarm_control_panel_condition_options_validation(
    hass: HomeAssistant,
    condition_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that alarm_control_panel conditions support the expected options."""
    await assert_condition_options_supported(
        hass,
        condition_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("alarm_control_panel"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="alarm_control_panel.is_armed",
            target_states=[
                AlarmControlPanelState.ARMED_AWAY,
                AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
                AlarmControlPanelState.ARMED_HOME,
                AlarmControlPanelState.ARMED_NIGHT,
                AlarmControlPanelState.ARMED_VACATION,
            ],
            other_states=[
                AlarmControlPanelState.ARMING,
                AlarmControlPanelState.DISARMED,
                AlarmControlPanelState.DISARMING,
                AlarmControlPanelState.PENDING,
                AlarmControlPanelState.TRIGGERED,
            ],
        ),
        *parametrize_condition_states_any(
            condition="alarm_control_panel.is_armed_away",
            target_states=[AlarmControlPanelState.ARMED_AWAY],
            other_states=other_states(AlarmControlPanelState.ARMED_AWAY),
            required_filter_attributes={
                ATTR_SUPPORTED_FEATURES: AlarmControlPanelEntityFeature.ARM_AWAY
            },
        ),
        *parametrize_condition_states_any(
            condition="alarm_control_panel.is_armed_home",
            target_states=[AlarmControlPanelState.ARMED_HOME],
            other_states=other_states(AlarmControlPanelState.ARMED_HOME),
            required_filter_attributes={
                ATTR_SUPPORTED_FEATURES: AlarmControlPanelEntityFeature.ARM_HOME
            },
        ),
        *parametrize_condition_states_any(
            condition="alarm_control_panel.is_armed_night",
            target_states=[AlarmControlPanelState.ARMED_NIGHT],
            other_states=other_states(AlarmControlPanelState.ARMED_NIGHT),
            required_filter_attributes={
                ATTR_SUPPORTED_FEATURES: AlarmControlPanelEntityFeature.ARM_NIGHT
            },
        ),
        *parametrize_condition_states_any(
            condition="alarm_control_panel.is_armed_vacation",
            target_states=[AlarmControlPanelState.ARMED_VACATION],
            other_states=other_states(AlarmControlPanelState.ARMED_VACATION),
            required_filter_attributes={
                ATTR_SUPPORTED_FEATURES: AlarmControlPanelEntityFeature.ARM_VACATION
            },
        ),
        *parametrize_condition_states_any(
            condition="alarm_control_panel.is_disarmed",
            target_states=[AlarmControlPanelState.DISARMED],
            other_states=other_states(AlarmControlPanelState.DISARMED),
        ),
        *parametrize_condition_states_any(
            condition="alarm_control_panel.is_triggered",
            target_states=[AlarmControlPanelState.TRIGGERED],
            other_states=other_states(AlarmControlPanelState.TRIGGERED),
        ),
    ],
)
async def test_alarm_control_panel_state_condition_behavior_any(
    hass: HomeAssistant,
    target_alarm_control_panels: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the alarm_control_panel state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_alarm_control_panels,
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
    parametrize_target_entities("alarm_control_panel"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="alarm_control_panel.is_armed",
            target_states=[
                AlarmControlPanelState.ARMED_AWAY,
                AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
                AlarmControlPanelState.ARMED_HOME,
                AlarmControlPanelState.ARMED_NIGHT,
                AlarmControlPanelState.ARMED_VACATION,
            ],
            other_states=[
                AlarmControlPanelState.ARMING,
                AlarmControlPanelState.DISARMED,
                AlarmControlPanelState.DISARMING,
                AlarmControlPanelState.PENDING,
                AlarmControlPanelState.TRIGGERED,
            ],
        ),
        *parametrize_condition_states_all(
            condition="alarm_control_panel.is_armed_away",
            target_states=[AlarmControlPanelState.ARMED_AWAY],
            other_states=other_states(AlarmControlPanelState.ARMED_AWAY),
            required_filter_attributes={
                ATTR_SUPPORTED_FEATURES: AlarmControlPanelEntityFeature.ARM_AWAY
            },
        ),
        *parametrize_condition_states_all(
            condition="alarm_control_panel.is_armed_home",
            target_states=[AlarmControlPanelState.ARMED_HOME],
            other_states=other_states(AlarmControlPanelState.ARMED_HOME),
            required_filter_attributes={
                ATTR_SUPPORTED_FEATURES: AlarmControlPanelEntityFeature.ARM_HOME
            },
        ),
        *parametrize_condition_states_all(
            condition="alarm_control_panel.is_armed_night",
            target_states=[AlarmControlPanelState.ARMED_NIGHT],
            other_states=other_states(AlarmControlPanelState.ARMED_NIGHT),
            required_filter_attributes={
                ATTR_SUPPORTED_FEATURES: AlarmControlPanelEntityFeature.ARM_NIGHT
            },
        ),
        *parametrize_condition_states_all(
            condition="alarm_control_panel.is_armed_vacation",
            target_states=[AlarmControlPanelState.ARMED_VACATION],
            other_states=other_states(AlarmControlPanelState.ARMED_VACATION),
            required_filter_attributes={
                ATTR_SUPPORTED_FEATURES: AlarmControlPanelEntityFeature.ARM_VACATION
            },
        ),
        *parametrize_condition_states_all(
            condition="alarm_control_panel.is_disarmed",
            target_states=[AlarmControlPanelState.DISARMED],
            other_states=other_states(AlarmControlPanelState.DISARMED),
        ),
        *parametrize_condition_states_all(
            condition="alarm_control_panel.is_triggered",
            target_states=[AlarmControlPanelState.TRIGGERED],
            other_states=other_states(AlarmControlPanelState.TRIGGERED),
        ),
    ],
)
async def test_alarm_control_panel_state_condition_behavior_all(
    hass: HomeAssistant,
    target_alarm_control_panels: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the alarm_control_panel state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_alarm_control_panels,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
