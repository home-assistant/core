"""Test for the switchbot_cloud relay switch & bot."""

from unittest.mock import patch

from switchbot_api import Device

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_relay_switch(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turn on and turn off."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="relay-switch-id-1",
            deviceName="relay-switch-1",
            deviceType="Relay Switch 1",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"switchStatus": 0}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "switch.relay_switch_1"
    assert hass.states.get(entity_id).state == STATE_OFF

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    assert hass.states.get(entity_id).state == STATE_ON

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_switchmode_bot(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turn on and turn off."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="bot-id-1",
            deviceName="bot-1",
            deviceType="Bot",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"deviceMode": "switchMode", "power": "off"}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "switch.bot_1"
    assert hass.states.get(entity_id).state == STATE_OFF

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    assert hass.states.get(entity_id).state == STATE_ON

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_pressmode_bot_no_switch_entity(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test a pressMode bot isn't added as a switch."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="bot-id-1",
            deviceName="bot-1",
            deviceType="Bot",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"deviceMode": "pressMode"}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert not hass.states.async_entity_ids(SWITCH_DOMAIN)


async def test_switch_relay_2pm_turn_on(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test switch relay 2pm turn on."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="relay-switch-id-1",
            deviceName="relay-switch-1",
            deviceType="Relay Switch 2PM",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"switchStatus": 0}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "switch.relay_switch_1_channel_1"
    assert hass.states.get(entity_id).state == STATE_OFF

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_called_once()


async def test_switch_relay_2pm_turn_off(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test switch relay 2pm turn off."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="relay-switch-id-1",
            deviceName="relay-switch-1",
            deviceType="Relay Switch 2PM",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"switchStatus": 0}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "switch.relay_switch_1_channel_1"
    assert hass.states.get(entity_id).state == STATE_OFF

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_called_once()


async def test_switch_relay_2pm_coordination_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test switch relay 2pm coordination is none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="relay-switch-id-1",
            deviceName="relay-switch-1",
            deviceType="Relay Switch 2PM",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = None

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "switch.relay_switch_1_channel_1"
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
