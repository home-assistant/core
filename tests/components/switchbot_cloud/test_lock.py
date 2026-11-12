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
    STATE_UNKNOWN,
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
        ("Smart Lock Ultra Max", 7),
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
        ("Smart Lock Ultra Max", 3),
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


@pytest.mark.parametrize(
    ("lock_state", "expected_state"),
    [
        ("locked", LockState.LOCKED),
        ("unlocked", LockState.UNLOCKED),
        ("locking", LockState.LOCKING),
        ("unlocking", LockState.UNLOCKING),
        ("jammed", LockState.JAMMED),
        ("latchBoltLocked", LockState.LOCKED),
        ("halfLocked", LockState.LOCKED),
        # The webhook reports the very same states upper cased
        ("LOCKED", LockState.LOCKED),
        ("JAMMED", LockState.JAMMED),
        # Anything the cloud adds later is unknown rather than unlocked
        ("somethingNew", STATE_UNKNOWN),
    ],
)
async def test_lock_states(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    lock_state: str,
    expected_state: str,
) -> None:
    """Test every lock state the cloud reports."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="lock-id-1",
            deviceName="lock-1",
            deviceType="Smart Lock Ultra",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"lockState": lock_state}

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("lock.lock_1").state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_LOCK, LockState.LOCKED),
        (SERVICE_UNLOCK, LockState.UNLOCKED),
        (SERVICE_OPEN, LockState.UNLOCKED),
    ],
)
async def test_command_replaces_a_jam(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    service: str,
    expected_state: str,
) -> None:
    """Test a command clears the jam instead of leaving it standing."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="lock-id-1",
            deviceName="lock-1",
            deviceType="Smart Lock Ultra",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"lockState": "jammed"}

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    lock_id = "lock.lock_1"
    assert hass.states.get(lock_id).state == LockState.JAMMED

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            LOCK_DOMAIN, service, {ATTR_ENTITY_ID: lock_id}, blocking=True
        )
    assert hass.states.get(lock_id).state == expected_state
