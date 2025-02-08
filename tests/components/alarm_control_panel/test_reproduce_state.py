"""Test reproduce state for Alarm control panel."""

import pytest

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import (
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Alarm control panel states."""
    hass.states.async_set(
        "alarm_control_panel.entity_armed_away",
        AlarmControlPanelState.ARMED_AWAY,
        {},
    )
    hass.states.async_set(
        "alarm_control_panel.entity_armed_custom_bypass",
        AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        {},
    )
    hass.states.async_set(
        "alarm_control_panel.entity_armed_home",
        AlarmControlPanelState.ARMED_HOME,
        {},
    )
    hass.states.async_set(
        "alarm_control_panel.entity_armed_night",
        AlarmControlPanelState.ARMED_NIGHT,
        {},
    )
    hass.states.async_set(
        "alarm_control_panel.entity_armed_vacation",
        AlarmControlPanelState.ARMED_VACATION,
        {},
    )
    hass.states.async_set(
        "alarm_control_panel.entity_disarmed", AlarmControlPanelState.DISARMED, {}
    )
    hass.states.async_set(
        "alarm_control_panel.entity_triggered",
        AlarmControlPanelState.TRIGGERED,
        {},
    )

    arm_away_calls = async_mock_service(
        hass, "alarm_control_panel", SERVICE_ALARM_ARM_AWAY
    )
    arm_custom_bypass_calls = async_mock_service(
        hass, "alarm_control_panel", SERVICE_ALARM_ARM_CUSTOM_BYPASS
    )
    arm_home_calls = async_mock_service(
        hass, "alarm_control_panel", SERVICE_ALARM_ARM_HOME
    )
    arm_night_calls = async_mock_service(
        hass, "alarm_control_panel", SERVICE_ALARM_ARM_NIGHT
    )
    arm_vacation_calls = async_mock_service(
        hass, "alarm_control_panel", SERVICE_ALARM_ARM_VACATION
    )
    disarm_calls = async_mock_service(hass, "alarm_control_panel", SERVICE_ALARM_DISARM)
    trigger_calls = async_mock_service(
        hass, "alarm_control_panel", SERVICE_ALARM_TRIGGER
    )

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State(
                "alarm_control_panel.entity_armed_away",
                AlarmControlPanelState.ARMED_AWAY,
            ),
            State(
                "alarm_control_panel.entity_armed_custom_bypass",
                AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
            ),
            State(
                "alarm_control_panel.entity_armed_home",
                AlarmControlPanelState.ARMED_HOME,
            ),
            State(
                "alarm_control_panel.entity_armed_night",
                AlarmControlPanelState.ARMED_NIGHT,
            ),
            State(
                "alarm_control_panel.entity_armed_vacation",
                AlarmControlPanelState.ARMED_VACATION,
            ),
            State(
                "alarm_control_panel.entity_disarmed",
                AlarmControlPanelState.DISARMED,
            ),
            State(
                "alarm_control_panel.entity_triggered",
                AlarmControlPanelState.TRIGGERED,
            ),
        ],
    )

    assert len(arm_away_calls) == 0
    assert len(arm_custom_bypass_calls) == 0
    assert len(arm_home_calls) == 0
    assert len(arm_night_calls) == 0
    assert len(arm_vacation_calls) == 0
    assert len(disarm_calls) == 0
    assert len(trigger_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(
        hass, [State("alarm_control_panel.entity_triggered", "not_supported")]
    )

    assert "not_supported" in caplog.text
    assert len(arm_away_calls) == 0
    assert len(arm_custom_bypass_calls) == 0
    assert len(arm_home_calls) == 0
    assert len(arm_night_calls) == 0
    assert len(arm_vacation_calls) == 0
    assert len(disarm_calls) == 0
    assert len(trigger_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State(
                "alarm_control_panel.entity_armed_away",
                AlarmControlPanelState.TRIGGERED,
            ),
            State(
                "alarm_control_panel.entity_armed_custom_bypass",
                AlarmControlPanelState.ARMED_AWAY,
            ),
            State(
                "alarm_control_panel.entity_armed_home",
                AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
            ),
            State(
                "alarm_control_panel.entity_armed_night",
                AlarmControlPanelState.ARMED_HOME,
            ),
            State(
                "alarm_control_panel.entity_armed_vacation",
                AlarmControlPanelState.ARMED_NIGHT,
            ),
            State(
                "alarm_control_panel.entity_disarmed",
                AlarmControlPanelState.ARMED_VACATION,
            ),
            State(
                "alarm_control_panel.entity_triggered",
                AlarmControlPanelState.DISARMED,
            ),
            # Should not raise
            State("alarm_control_panel.non_existing", "on"),
        ],
    )

    assert len(arm_away_calls) == 1
    assert arm_away_calls[0].domain == "alarm_control_panel"
    assert arm_away_calls[0].data == {
        "entity_id": "alarm_control_panel.entity_armed_custom_bypass"
    }

    assert len(arm_custom_bypass_calls) == 1
    assert arm_custom_bypass_calls[0].domain == "alarm_control_panel"
    assert arm_custom_bypass_calls[0].data == {
        "entity_id": "alarm_control_panel.entity_armed_home"
    }

    assert len(arm_home_calls) == 1
    assert arm_home_calls[0].domain == "alarm_control_panel"
    assert arm_home_calls[0].data == {
        "entity_id": "alarm_control_panel.entity_armed_night"
    }

    assert len(arm_night_calls) == 1
    assert arm_night_calls[0].domain == "alarm_control_panel"
    assert arm_night_calls[0].data == {
        "entity_id": "alarm_control_panel.entity_armed_vacation"
    }

    assert len(arm_vacation_calls) == 1
    assert arm_vacation_calls[0].domain == "alarm_control_panel"
    assert arm_vacation_calls[0].data == {
        "entity_id": "alarm_control_panel.entity_disarmed"
    }

    assert len(disarm_calls) == 1
    assert disarm_calls[0].domain == "alarm_control_panel"
    assert disarm_calls[0].data == {"entity_id": "alarm_control_panel.entity_triggered"}

    assert len(trigger_calls) == 1
    assert trigger_calls[0].domain == "alarm_control_panel"
    assert trigger_calls[0].data == {
        "entity_id": "alarm_control_panel.entity_armed_away"
    }
