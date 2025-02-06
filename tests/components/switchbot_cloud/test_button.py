"""Test for the switchbot_cloud bot as a button."""

from unittest.mock import patch

from switchbot_api import BotCommands, Device

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
            "bot-id-1", BotCommands.PRESS, "command", "default"
        )

    assert hass.states.get(entity_id).state != STATE_UNKNOWN


async def test_switchmode_bot_no_button_entity(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test a switchMode bot isn't added as a button."""
    mock_list_devices.return_value = [
        Device(
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
