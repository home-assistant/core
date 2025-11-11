"""Test alarm control panel trigger."""

from homeassistant.components import automation
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.const import CONF_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component


async def test_alarm_armed_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the alarm armed trigger fires when an alarm is armed."""
    entity_id = "alarm_control_panel.test_alarm"
    await async_setup_component(hass, "alarm_control_panel", {})

    # Set initial state
    hass.states.async_set(entity_id, AlarmControlPanelState.DISARMED)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "alarm_control_panel.armed",
                    "target": {CONF_ENTITY_ID: entity_id},
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Trigger armed home
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_HOME)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Trigger armed away
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_AWAY)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Trigger armed night
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_NIGHT)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Trigger armed vacation
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_VACATION)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Trigger armed custom bypass
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_CUSTOM_BYPASS)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id


async def test_alarm_armed_trigger_with_mode_filter(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the alarm armed trigger with mode filter."""
    entity_id = "alarm_control_panel.test_alarm"
    await async_setup_component(hass, "alarm_control_panel", {})

    # Set initial state
    hass.states.async_set(entity_id, AlarmControlPanelState.DISARMED)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "alarm_control_panel.armed",
                    "target": {
                        CONF_ENTITY_ID: entity_id,
                    },
                    "options": {
                        "mode": [
                            AlarmControlPanelState.ARMED_HOME,
                            AlarmControlPanelState.ARMED_AWAY,
                        ],
                    },
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Trigger matching armed home mode
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_HOME)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Trigger matching armed away mode
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_AWAY)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Trigger non-matching armed night mode - should not trigger
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_NIGHT)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Trigger non-matching armed vacation mode - should not trigger
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_VACATION)
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_alarm_armed_trigger_ignores_unavailable(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the alarm armed trigger ignores unavailable states."""
    entity_id = "alarm_control_panel.test_alarm"
    await async_setup_component(hass, "alarm_control_panel", {})

    # Set initial state
    hass.states.async_set(entity_id, AlarmControlPanelState.DISARMED)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "alarm_control_panel.armed",
                    "target": {
                        CONF_ENTITY_ID: entity_id,
                    },
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Set to unavailable - should not trigger
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Trigger armed after unavailable - should trigger
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_HOME)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id


async def test_alarm_armed_trigger_ignores_non_armed_states(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the alarm armed trigger ignores non-armed states."""
    entity_id = "alarm_control_panel.test_alarm"
    await async_setup_component(hass, "alarm_control_panel", {})

    # Set initial state
    hass.states.async_set(entity_id, AlarmControlPanelState.DISARMED)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "alarm_control_panel.armed",
                    "target": {
                        CONF_ENTITY_ID: entity_id,
                    },
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Set to disarmed - should not trigger
    hass.states.async_set(entity_id, AlarmControlPanelState.DISARMED)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Set to triggered - should not trigger
    hass.states.async_set(entity_id, AlarmControlPanelState.TRIGGERED)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Set to arming - should not trigger
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMING)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Set to pending - should not trigger
    hass.states.async_set(entity_id, AlarmControlPanelState.PENDING)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Set to disarming - should not trigger
    hass.states.async_set(entity_id, AlarmControlPanelState.DISARMING)
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_alarm_armed_trigger_from_unknown_state(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the trigger fires when entity goes from unknown/None to first armed state."""
    entity_id = "alarm_control_panel.test_alarm"
    await async_setup_component(hass, "alarm_control_panel", {})

    # Do NOT set any initial state - entity starts with None state

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "alarm_control_panel.armed",
                    "target": {CONF_ENTITY_ID: entity_id},
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # First armed state should trigger even though entity had no previous state
    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_HOME)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
