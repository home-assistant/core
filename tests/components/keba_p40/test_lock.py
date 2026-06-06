"""Tests for the KEBA P40 socket lock."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_client", "entity_registry_enabled_by_default")
async def test_lock(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the socket lock via snapshot."""
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_lock_unlock_calls(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lock/unlock call the client."""
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.garage_socket_lock"},
        blocking=True,
    )
    mock_client.lock.assert_called_once_with("21900042")

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.garage_socket_lock"},
        blocking=True,
    )
    mock_client.unlock.assert_called_once_with("21900042")
