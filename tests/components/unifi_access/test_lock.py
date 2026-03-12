"""Tests for the UniFi Access lock platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from unifi_access_api import ApiError

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def test_lock_entities_created(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test lock entities are created for each door."""
    state = hass.states.get("lock.front_door")
    assert state is not None
    assert state.state == LockState.LOCKED

    state = hass.states.get("lock.back_door")
    assert state is not None
    assert state.state == LockState.UNLOCKED


async def test_unlock_door(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test unlocking a door."""
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.front_door"},
        blocking=True,
    )

    mock_client.unlock_door.assert_awaited_once_with("door-001")


async def test_unlock_door_api_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test unlocking a door raises on API error."""
    mock_client.unlock_door.side_effect = ApiError("unlock failed")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: "lock.front_door"},
            blocking=True,
        )


async def test_lock_not_supported(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test locking a door raises HomeAssistantError."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: "lock.front_door"},
            blocking=True,
        )
