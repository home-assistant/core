"""Test ESPHome alarm_control_panels."""

from unittest.mock import call

from aioesphomeapi import (
    AlarmControlPanelCommand,
    AlarmControlPanelEntityState as ESPHomeAlarmEntityState,
    AlarmControlPanelInfo,
    AlarmControlPanelState as ESPHomeAlarmState,
    APIClient,
)

from homeassistant.components.alarm_control_panel import (
    ATTR_CODE,
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    AlarmControlPanelState,
)
from homeassistant.components.esphome.alarm_control_panel import EspHomeACPFeatures
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import MockGenericDeviceEntryType


async def test_generic_alarm_control_panel_requires_code(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic alarm_control_panel entity that requires a code."""
    entity_info = [
        AlarmControlPanelInfo(
            object_id="myalarm_control_panel",
            key=1,
            name="my alarm_control_panel",
            unique_id="my_alarm_control_panel",
            supported_features=EspHomeACPFeatures.ARM_AWAY
            | EspHomeACPFeatures.ARM_CUSTOM_BYPASS
            | EspHomeACPFeatures.ARM_HOME
            | EspHomeACPFeatures.ARM_NIGHT
            | EspHomeACPFeatures.ARM_VACATION
            | EspHomeACPFeatures.TRIGGER,
            requires_code=True,
            requires_code_to_arm=True,
        )
    ]
    states = [ESPHomeAlarmEntityState(key=1, state=ESPHomeAlarmState.ARMED_AWAY)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("alarm_control_panel.test_myalarm_control_panel")
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_myalarm_control_panel",
            ATTR_CODE: 1234,
        },
        blocking=True,
    )
    mock_client.alarm_control_panel_command.assert_has_calls(
        [call(1, AlarmControlPanelCommand.ARM_AWAY, "1234")]
    )
    mock_client.alarm_control_panel_command.reset_mock()

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_myalarm_control_panel",
            ATTR_CODE: 1234,
        },
        blocking=True,
    )
    mock_client.alarm_control_panel_command.assert_has_calls(
        [call(1, AlarmControlPanelCommand.ARM_CUSTOM_BYPASS, "1234")]
    )
    mock_client.alarm_control_panel_command.reset_mock()

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_myalarm_control_panel",
            ATTR_CODE: 1234,
        },
        blocking=True,
    )
    mock_client.alarm_control_panel_command.assert_has_calls(
        [call(1, AlarmControlPanelCommand.ARM_HOME, "1234")]
    )
    mock_client.alarm_control_panel_command.reset_mock()

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_NIGHT,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_myalarm_control_panel",
            ATTR_CODE: 1234,
        },
        blocking=True,
    )
    mock_client.alarm_control_panel_command.assert_has_calls(
        [call(1, AlarmControlPanelCommand.ARM_NIGHT, "1234")]
    )
    mock_client.alarm_control_panel_command.reset_mock()

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_VACATION,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_myalarm_control_panel",
            ATTR_CODE: 1234,
        },
        blocking=True,
    )
    mock_client.alarm_control_panel_command.assert_has_calls(
        [call(1, AlarmControlPanelCommand.ARM_VACATION, "1234")]
    )
    mock_client.alarm_control_panel_command.reset_mock()

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_TRIGGER,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_myalarm_control_panel",
            ATTR_CODE: 1234,
        },
        blocking=True,
    )
    mock_client.alarm_control_panel_command.assert_has_calls(
        [call(1, AlarmControlPanelCommand.TRIGGER, "1234")]
    )
    mock_client.alarm_control_panel_command.reset_mock()

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_DISARM,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_myalarm_control_panel",
            ATTR_CODE: 1234,
        },
        blocking=True,
    )
    mock_client.alarm_control_panel_command.assert_has_calls(
        [call(1, AlarmControlPanelCommand.DISARM, "1234")]
    )
    mock_client.alarm_control_panel_command.reset_mock()


async def test_generic_alarm_control_panel_no_code(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic alarm_control_panel entity that does not require a code."""
    entity_info = [
        AlarmControlPanelInfo(
            object_id="myalarm_control_panel",
            key=1,
            name="my alarm_control_panel",
            unique_id="my_alarm_control_panel",
            supported_features=EspHomeACPFeatures.ARM_AWAY
            | EspHomeACPFeatures.ARM_CUSTOM_BYPASS
            | EspHomeACPFeatures.ARM_HOME
            | EspHomeACPFeatures.ARM_NIGHT
            | EspHomeACPFeatures.ARM_VACATION
            | EspHomeACPFeatures.TRIGGER,
            requires_code=False,
            requires_code_to_arm=False,
        )
    ]
    states = [ESPHomeAlarmEntityState(key=1, state=ESPHomeAlarmState.ARMED_AWAY)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("alarm_control_panel.test_myalarm_control_panel")
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: "alarm_control_panel.test_myalarm_control_panel"},
        blocking=True,
    )
    mock_client.alarm_control_panel_command.assert_has_calls(
        [call(1, AlarmControlPanelCommand.DISARM, None)]
    )
    mock_client.alarm_control_panel_command.reset_mock()


async def test_generic_alarm_control_panel_missing_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic alarm_control_panel entity that is missing state."""
    entity_info = [
        AlarmControlPanelInfo(
            object_id="myalarm_control_panel",
            key=1,
            name="my alarm_control_panel",
            unique_id="my_alarm_control_panel",
            supported_features=EspHomeACPFeatures.ARM_AWAY
            | EspHomeACPFeatures.ARM_CUSTOM_BYPASS
            | EspHomeACPFeatures.ARM_HOME
            | EspHomeACPFeatures.ARM_NIGHT
            | EspHomeACPFeatures.ARM_VACATION
            | EspHomeACPFeatures.TRIGGER,
            requires_code=False,
            requires_code_to_arm=False,
        )
    ]
    states = []
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("alarm_control_panel.test_myalarm_control_panel")
    assert state is not None
    assert state.state == STATE_UNKNOWN
