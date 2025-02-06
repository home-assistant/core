"""Test for the switchbot_cloud lock."""

from unittest.mock import patch

from switchbot_api import Device

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_lock(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            deviceId="lock-id-1",
            deviceName="lock-1",
            deviceType="Smart Lock",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"lockState": "locked"}

    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    lock_id = "lock.lock_1"
    assert hass.states.get(lock_id).state == LockState.LOCKED

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            LOCK_DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: lock_id}, blocking=True
        )
    assert hass.states.get(lock_id).state == LockState.UNLOCKED

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            LOCK_DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: lock_id}, blocking=True
        )
    assert hass.states.get(lock_id).state == LockState.LOCKED
