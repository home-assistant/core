"""Test for the switchbot_cloud relay switch."""

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
)
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_relay_switch(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turn on and turn off."""
    mock_list_devices.return_value = [
        Device(
            deviceId="relay-switch-id-1",
            deviceName="relay-switch-1",
            deviceType="Relay Switch 1",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"switchStatus": 0}

    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

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
