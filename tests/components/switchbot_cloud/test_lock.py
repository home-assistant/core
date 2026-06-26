"""Test for the switchbot_cloud lock."""

from unittest.mock import patch

import pytest
from switchbot_api import Device

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
)
from homeassistant.core import HomeAssistant

from . import configure_integration


@pytest.mark.parametrize(
    ("device_info", "test_index"),
    [
        ("Smart Lock", 0),
        ("Smart Lock Lite", 1),
        ("Smart Lock Pro", 2),
        ("Smart Lock Ultra", 3),
        ("Lock Vision", 4),
        ("Lock Vision Pro", 5),
        ("Smart Lock Pro Wifi", 6),
    ],
)
async def test_lock(
    hass: HomeAssistant, mock_list_devices, mock_get_status, device_info, test_index
) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="lock-id-1",
            deviceName="lock-1",
            deviceType=device_info,
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"lockState": "locked"}

    entry = await configure_integration(hass)

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


@pytest.mark.parametrize(
    ("device_info", "test_index"),
    [
        ("Smart Lock", 0),
        ("Smart Lock Pro", 1),
        ("Smart Lock Ultra", 2),
        ("Lock Vision", 3),
        ("Lock Vision Pro", 4),
        ("Smart Lock Pro Wifi", 5),
    ],
)
async def test_lock_open(
    hass: HomeAssistant, mock_list_devices, mock_get_status, device_info, test_index
) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="lock-id-1",
            deviceName="lock-1",
            deviceType=device_info,
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"lockState": "locked"}

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    lock_id = "lock.lock_1"
    assert hass.states.get(lock_id).state == LockState.LOCKED

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            LOCK_DOMAIN, SERVICE_OPEN, {ATTR_ENTITY_ID: lock_id}, blocking=True
        )
    assert hass.states.get(lock_id).state == LockState.UNLOCKED
