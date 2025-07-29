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
            deviceId="light-id-1",
            deviceName="light-1",
            deviceType="Strip Light",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [None]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "light.light_1"
    state = hass.states.get(entity_id)
    assert state.state is STATE_UNKNOWN


async def test_strip_light_turn_off(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test strip light turn off."""

    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="light-id-1",
            deviceName="light-1",
            deviceType="Strip Light",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "brightness": 1, "color": "0:0:0", "colorTemperature": 4567},
        {"power": "off", "brightness": 10, "color": "0:0:0", "colorTemperature": 5555},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "light.light_1"
    # state = hass.states.get(entity_id)

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called_once()
    state = hass.states.get(entity_id)
    assert state.state is STATE_OFF


async def test_rgbww_light_turn_off(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test rgbww light turn_off."""

    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="light-id-1",
            deviceName="light-1",
            deviceType="Strip Light 3",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "brightness": 1, "color": "0:0:0", "colorTemperature": 4567},
        {"power": "off", "brightness": 10, "color": "0:0:0", "colorTemperature": 5555},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "light.light_1"

    with (
        patch.object(SwitchBotAPI, "send_command") as mock_send_command,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called_once()
    state = hass.states.get(entity_id)
    assert state.state is STATE_OFF


async def test_strip_light_turn_on(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test strip light turn on."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="light-id-1",
            deviceName="light-1",
            deviceType="Strip Light",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "brightness": 1, "color": "0:0:0", "colorTemperature": 4567},
        {"power": "on", "brightness": 10, "color": "0:0:0", "colorTemperature": 5555},
        {
            "power": "on",
            "brightness": 10,
            "color": "255:255:255",
            "colorTemperature": 5555,
        },
        {
            "power": "on",
            "brightness": 10,
            "color": "255:255:255",
            "colorTemperature": 5555,
        },
        {
            "power": "on",
            "brightness": 10,
            "color": "255:255:255",
            "colorTemperature": 5555,
        },
        {
            "power": "on",
            "brightness": 10,
            "color": "255:255:255",
            "colorTemperature": 5555,
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "light.light_1"
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

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_send_command.assert_called()
    state = hass.states.get(entity_id)
    assert state.state is STATE_ON


async def test_rgbww_light_turn_on(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test rgbww light turn on."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="light-id-1",
            deviceName="light-1",
            deviceType="Strip Light 3",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "brightness": 1, "color": "0:0:0", "colorTemperature": 4567},
        {"power": "on", "brightness": 10, "color": "0:0:0", "colorTemperature": 5555},
        {
            "power": "on",
            "brightness": 10,
            "color": "255:255:255",
            "colorTemperature": 5555,
        },
        {
            "power": "on",
            "brightness": 10,
            "color": "255:255:255",
            "colorTemperature": 5555,
        },
        {
            "power": "on",
            "brightness": 10,
            "color": "255:255:255",
            "colorTemperature": 5555,
        },
        {
            "power": "on",
            "brightness": 10,
            "color": "255:255:255",
            "colorTemperature": 5555,
        },
        {
            "power": "on",
            "brightness": 10,
            "color": "255:255:255",
            "colorTemperature": 5555,
        },
        {
            "power": "on",
            "brightness": 10,
            "color": "255:255:255",
            "colorTemperature": 5555,
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "light.light_1"
    state = hass.states.get(entity_id)
    assert state.state is STATE_OFF
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, "color_temp_kelvin": 2800},
            blocking=True,
        )
        mock_send_command.assert_called()
    state = hass.states.get(entity_id)
    assert state.state is STATE_ON

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
            {ATTR_ENTITY_ID: entity_id},
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
