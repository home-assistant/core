"""Test for the Switchbot Battery Circulator Fan."""

from unittest.mock import patch

from switchbot_api import Device, SwitchBotAPI

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_coordinator_data_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test coordinator data is none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        None,
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_UNKNOWN


async def test_turn_on(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """Test turning on the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_OFF

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_called()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_turn_off(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning off the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "off", "mode": "direct", "fanSpeed": "0"},
        {"power": "off", "mode": "direct", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_called()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_set_percentage(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test set percentage."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "off", "mode": "direct", "fanSpeed": "5"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 5},
            blocking=True,
        )
    mock_send_command.assert_called()


async def test_set_preset_mode(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test set preset mode."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "baby", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: "baby"},
            blocking=True,
        )
    mock_send_command.assert_called_once()
