"""Test for the switchbot_cloud bot as a button."""

from unittest.mock import patch

import pytest
from switchbot_api import BotCommands, Device
from switchbot_api.commands import ArtFrameCommands

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_pressmode_bot(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test press."""
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

    entity_id = "button.bot_1"
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called_once_with(
            "bot-id-1", BotCommands.PRESS.value, "command", "default"
        )

    assert hass.states.get(entity_id).state != STATE_UNKNOWN


async def test_switchmode_bot_no_button_entity(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test a switchMode bot isn't added as a button."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="bot-id-1",
            deviceName="bot-1",
            deviceType="Bot",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"deviceMode": "switchMode"}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert not hass.states.async_entity_ids(BUTTON_DOMAIN)


@pytest.mark.parametrize(
    "buttons",
    [
        ("AI Art Frame", ArtFrameCommands.PREVIOUS),
        ("AI Art Frame", ArtFrameCommands.NEXT),
    ],
)
async def test_loaded_buttons(
    hass: HomeAssistant, mock_list_devices, mock_get_status, buttons
) -> None:
    """Test press."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="device_id",
            deviceName="device_name",
            deviceType=buttons[0],
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {
        "deviceType": buttons[0],
    }

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = f"button.device_name_{buttons[1].value}"
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called()

    assert hass.states.get(entity_id).state != STATE_UNKNOWN
