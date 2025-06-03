"""Test ESPHome locks."""

from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    LockCommand,
    LockEntityState,
    LockInfo,
    LockState as ESPHomeLockState,
)

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import MockGenericDeviceEntryType


async def test_lock_entity_no_open(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic lock entity that does not support open."""
    entity_info = [
        LockInfo(
            object_id="mylock",
            key=1,
            name="my lock",
            unique_id="my_lock",
            supports_open=False,
            requires_code=False,
        )
    ]
    states = [LockEntityState(key=1, state=ESPHomeLockState.UNLOCKING)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("lock.test_mylock")
    assert state is not None
    assert state.state == LockState.UNLOCKING

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.test_mylock"},
        blocking=True,
    )
    mock_client.lock_command.assert_has_calls([call(1, LockCommand.LOCK)])
    mock_client.lock_command.reset_mock()


async def test_lock_entity_start_locked(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic lock entity that does not support open."""
    entity_info = [
        LockInfo(
            object_id="mylock",
            key=1,
            name="my lock",
            unique_id="my_lock",
        )
    ]
    states = [LockEntityState(key=1, state=ESPHomeLockState.LOCKED)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("lock.test_mylock")
    assert state is not None
    assert state.state == LockState.LOCKED


async def test_lock_entity_supports_open(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic lock entity that supports open."""
    entity_info = [
        LockInfo(
            object_id="mylock",
            key=1,
            name="my lock",
            unique_id="my_lock",
            supports_open=True,
            requires_code=True,
        )
    ]
    states = [LockEntityState(key=1, state=ESPHomeLockState.LOCKING)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("lock.test_mylock")
    assert state is not None
    assert state.state == LockState.LOCKING

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.test_mylock"},
        blocking=True,
    )
    mock_client.lock_command.assert_has_calls([call(1, LockCommand.LOCK)])
    mock_client.lock_command.reset_mock()

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.test_mylock"},
        blocking=True,
    )
    mock_client.lock_command.assert_has_calls([call(1, LockCommand.UNLOCK, None)])

    mock_client.lock_command.reset_mock()
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_OPEN,
        {ATTR_ENTITY_ID: "lock.test_mylock"},
        blocking=True,
    )
    mock_client.lock_command.assert_has_calls([call(1, LockCommand.OPEN)])
