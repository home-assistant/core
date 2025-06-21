"""Test for the Switchbot Light Entity."""

from unittest.mock import patch

from switchbot_api import Device, SwitchBotAPI

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_light_turn_off_1(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning off the off."""

    device_type = "Strip Light"
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="light-id-1",
            deviceName="light-1",
            deviceType=device_type,
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "brightness": 1, "color": "0:0:0", "colorTemperature": 4567},
        {"power": "off", "brightness": 10, "color": "0:0:0", "colorTemperature": 5555},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "light.light_1_none"
    state = hass.states.get(entity_id)
    assert state.state is STATE_OFF


async def test_light_turn_off_2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning off the off."""
    device_type = "Strip Light 3"
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="light-id-1",
            deviceName="light-1",
            deviceType=device_type,
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "brightness": 1, "color": "0:0:0", "colorTemperature": 4567},
        {"power": "off", "brightness": 10, "color": "0:0:0", "colorTemperature": 5555},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "light.light_1_none"
    state = hass.states.get(entity_id)
    assert state.state is STATE_OFF


async def test_light_turn_off_3(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning off the off."""
    device_type = "Strip Light 3"
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="light-id-1",
            deviceName="light-1",
            deviceType=device_type,
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "on", "brightness": 1, "color": "0:0:0", "colorTemperature": 4567},
        {"power": "off", "brightness": 10, "color": "0:0:0", "colorTemperature": 5555},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "light.light_1_none"
    state = hass.states.get(entity_id)
    assert state.state is STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_not_called()
    state = hass.states.get(entity_id)
    assert state.state is STATE_OFF


async def test_light_turn_off_4(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning off the off."""
    device_type = "Strip Light 3"
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="light-id-1",
            deviceName="light-1",
            deviceType=device_type,
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "on", "brightness": 1, "color": "0:0:0", "colorTemperature": 4567},
        {"power": "on", "brightness": 10, "color": "0:0:0", "colorTemperature": 5555},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "light.light_1_none"
    state = hass.states.get(entity_id)
    assert state.state is STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called()
    state = hass.states.get(entity_id)
    assert state.state is STATE_OFF


async def test_light_turn_on_1(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning off the off."""
    device_type = "Strip Light 3"
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="light-id-1",
            deviceName="light-1",
            deviceType=device_type,
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "brightness": 1, "color": "0:0:0", "colorTemperature": 4567},
        {"power": "on", "brightness": 10, "color": "0:0:0", "colorTemperature": 5555},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "light.light_1_none"
    state = hass.states.get(entity_id)
    assert state.state is STATE_OFF
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, "brightness": 99},
            blocking=True,
        )
        mock_send_command.assert_called()
    state = hass.states.get(entity_id)
    assert state.state is STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, "rgb_color": (255, 246, 158)},
            blocking=True,
        )
        mock_send_command.assert_called()
    state = hass.states.get(entity_id)
    assert state.state is STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, "color_temp_kelvin": 3333},
            blocking=True,
        )
        mock_send_command.assert_called()
    state = hass.states.get(entity_id)
    assert state.state is STATE_ON
