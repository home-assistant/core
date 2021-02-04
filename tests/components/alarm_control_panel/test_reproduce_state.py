"""Test reproduce state for Alarm control panel."""
from homeassistant.const import (
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import State

from tests.common import async_mock_service


async def test_reproducing_states(hass, caplog):
    """Test reproducing Alarm control panel states."""
    hass.states.async_set(
        "alarm_control_panel.entity_armed_away", STATE_ALARM_ARMED_AWAY, {}
    )
    hass.states.async_set(
        "alarm_control_panel.entity_armed_custom_bypass",
        STATE_ALARM_ARMED_CUSTOM_BYPASS,
        {},
    )
    hass.states.async_set(
        "alarm_control_panel.entity_armed_home", STATE_ALARM_ARMED_HOME, {}
    )
    hass.states.async_set(
        "alarm_control_panel.entity_armed_night", STATE_ALARM_ARMED_NIGHT, {}
    )
    hass.states.async_set(
        "alarm_control_panel.entity_disarmed", STATE_ALARM_DISARMED, {}
    )
    hass.states.async_set(
        "alarm_control_panel.entity_triggered", STATE_ALARM_TRIGGERED, {}
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
    disarm_calls = async_mock_service(hass, "alarm_control_panel", SERVICE_ALARM_DISARM)
    trigger_calls = async_mock_service(
        hass, "alarm_control_panel", SERVICE_ALARM_TRIGGER
    )

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("alarm_control_panel.entity_armed_away", STATE_ALARM_ARMED_AWAY),
            State(
                "alarm_control_panel.entity_armed_custom_bypass",
                STATE_ALARM_ARMED_CUSTOM_BYPASS,
            ),
            State("alarm_control_panel.entity_armed_home", STATE_ALARM_ARMED_HOME),
            State("alarm_control_panel.entity_armed_night", STATE_ALARM_ARMED_NIGHT),
            State("alarm_control_panel.entity_disarmed", STATE_ALARM_DISARMED),
            State("alarm_control_panel.entity_triggered", STATE_ALARM_TRIGGERED),
        ]
    )

    assert len(arm_away_calls) == 0
    assert len(arm_custom_bypass_calls) == 0
    assert len(arm_home_calls) == 0
    assert len(arm_night_calls) == 0
    assert len(disarm_calls) == 0
    assert len(trigger_calls) == 0

    # Test invalid state is handled
    await hass.helpers.state.async_reproduce_state(
        [State("alarm_control_panel.entity_triggered", "not_supported")]
    )

    assert "not_supported" in caplog.text
    assert len(arm_away_calls) == 0
    assert len(arm_custom_bypass_calls) == 0
    assert len(arm_home_calls) == 0
    assert len(arm_night_calls) == 0
    assert len(disarm_calls) == 0
    assert len(trigger_calls) == 0

    # Make sure correct services are called
    await hass.helpers.state.async_reproduce_state(
        [
            State("alarm_control_panel.entity_armed_away", STATE_ALARM_TRIGGERED),
            State(
                "alarm_control_panel.entity_armed_custom_bypass", STATE_ALARM_ARMED_AWAY
            ),
            State(
                "alarm_control_panel.entity_armed_home", STATE_ALARM_ARMED_CUSTOM_BYPASS
            ),
            State("alarm_control_panel.entity_armed_night", STATE_ALARM_ARMED_HOME),
            State("alarm_control_panel.entity_disarmed", STATE_ALARM_ARMED_NIGHT),
            State("alarm_control_panel.entity_triggered", STATE_ALARM_DISARMED),
            # Should not raise
            State("alarm_control_panel.non_existing", "on"),
        ]
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
