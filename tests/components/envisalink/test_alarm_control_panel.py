"""Test the Envisalink alarm control panels."""

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.components.envisalink.const import DOMAIN
from homeassistant.components.envisalink.pyenvisalink.alarm_panel import (
    EnvisalinkAlarmPanel,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_alarm_control_panel_state(
    hass: HomeAssistant, mock_config_entry, init_integration
) -> None:
    """Test the createion and values of the Envisalink alarm control panels."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    er.async_get(hass)

    state = hass.states.get("alarm_control_panel.test_alarm_name_partition_1")
    assert state
    assert state.state == STATE_ALARM_DISARMED


@pytest.mark.parametrize(
    "json_key,alarm_state",
    [
        ("alarm", STATE_ALARM_TRIGGERED),
        ("armed_zero_entry_delay", STATE_ALARM_ARMED_NIGHT),
        ("armed_away", STATE_ALARM_ARMED_AWAY),
        ("armed_stay", STATE_ALARM_ARMED_HOME),
        ("exit_delay", STATE_ALARM_PENDING),
        ("entry_delay", STATE_ALARM_PENDING),
        ("alpha", STATE_ALARM_DISARMED),
    ],
)
async def test_alarm_control_panel_update(
    hass: HomeAssistant, mock_config_entry, init_integration, json_key, alarm_state
) -> None:
    """Test updating the alarm control panel's state."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    er.async_get(hass)

    controller.controller.alarm_state["partition"][1]["status"][json_key] = True
    controller.async_partition_updated_callback([1])
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_alarm_name_partition_1")
    assert state
    assert state.state == alarm_state


@pytest.mark.parametrize(
    "service_call,json_key,alarm_state,code",
    [
        ("alarm_trigger", "alarm", STATE_ALARM_TRIGGERED, 1234),
        ("alarm_trigger", "alarm", STATE_ALARM_TRIGGERED, None),
        ("alarm_arm_night", "armed_zero_entry_delay", STATE_ALARM_ARMED_NIGHT, 1234),
        ("alarm_arm_night", "armed_zero_entry_delay", STATE_ALARM_ARMED_NIGHT, None),
        ("alarm_arm_away", "armed_away", STATE_ALARM_ARMED_AWAY, 1234),
        ("alarm_arm_away", "armed_away", STATE_ALARM_ARMED_AWAY, None),
        ("alarm_arm_home", "armed_stay", STATE_ALARM_ARMED_HOME, 1234),
        ("alarm_arm_home", "armed_stay", STATE_ALARM_ARMED_HOME, None),
    ],
)
async def test_arming_modes(
    hass: HomeAssistant,
    mock_config_entry,
    init_integration,
    service_call,
    json_key,
    alarm_state,
    code,
) -> None:
    """Test disarming the alarm."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    er.async_get(hass)

    fields = {ATTR_ENTITY_ID: "alarm_control_panel.test_alarm_name_partition_1"}
    if code:
        fields["code"] = code

    with patch.object(
        EnvisalinkAlarmPanel,
        "arm_away_partition",
        autospec=True,
    ):
        # Arm alarm
        await hass.services.async_call(
            ALARM_DOMAIN,
            service_call,
            fields,
            blocking=True,
        )
        controller.controller.alarm_state["partition"][1]["status"][json_key] = True
        controller.async_partition_updated_callback([1])
        await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_alarm_name_partition_1")
    assert state
    assert state.state == alarm_state

    with patch.object(
        EnvisalinkAlarmPanel,
        "disarm_partition",
        autospec=True,
    ):
        # Disarm alarm
        await hass.services.async_call(
            ALARM_DOMAIN,
            "alarm_disarm",
            fields,
            blocking=True,
        )
        controller.controller.alarm_state["partition"][1]["status"][json_key] = False
        controller.controller.alarm_state["partition"][1]["status"]["alpha"] = True
        controller.async_partition_updated_callback([1])
        await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_alarm_name_partition_1")
    assert state
    assert state.state == STATE_ALARM_DISARMED


@pytest.mark.parametrize(
    "service_call,patch_name,fields,should_succeed",
    [
        ("alarm_keypress", "keypresses_to_partition", {}, False),
        ("alarm_keypress", "keypresses_to_partition", {"keypress": "*104#"}, True),
        (
            "alarm_keypress",
            "keypresses_to_partition",
            {"keypress": "*104#", "extra": "value"},
            False,
        ),
        ("invoke_custom_function", "command_output", {}, False),
        ("invoke_custom_function", "command_output", {"pgm": 2}, True),
        (
            "invoke_custom_function",
            "command_output",
            {"pgm": 2, "extra": "value"},
            False,
        ),
    ],
)
async def test_services(
    hass: HomeAssistant,
    mock_config_entry,
    init_integration,
    service_call,
    patch_name,
    fields,
    should_succeed,
) -> None:
    """Test sending keypresses to the panel."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    er.async_get(hass)

    with patch.object(
        EnvisalinkAlarmPanel,
        patch_name,
        autospec=True,
    ):
        success = True
        fields = fields | {
            ATTR_ENTITY_ID: "alarm_control_panel.test_alarm_name_partition_1"
        }
        try:
            await hass.services.async_call(
                DOMAIN,
                service_call,
                fields,
                blocking=True,
            )
            await hass.async_block_till_done()
        except vol.error.MultipleInvalid:
            success = False

        assert should_succeed == success
