"""Tests for the UniFi Access lock platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from unifi_access_api import ApiError

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_lock_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test lock entities are created with expected state."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


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


async def test_open_door(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test opening a door calls unlock."""
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_OPEN,
        {ATTR_ENTITY_ID: "lock.front_door"},
        blocking=True,
    )

    mock_client.unlock_door.assert_awaited_once_with("door-001")
