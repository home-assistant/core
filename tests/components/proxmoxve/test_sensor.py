"""Tests for the Proxmox VE sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_load_json_array_fixture,
    snapshot_platform,
)


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass,
            entity_registry,
            snapshot,
            mock_config_entry.entry_id,
        )


async def test_storage_missing_used_fraction(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test storage usage percentage sensor when used_fraction is missing."""
    storage_data = await async_load_json_array_fixture(
        hass, "nodes/storage.json", "proxmoxve"
    )
    # Remove used_fraction from all storage entries
    storage_without_fraction = [
        {key: value for key, value in storage.items() if key != "used_fraction"}
        for storage in storage_data
    ]
    mock_proxmox_client._node_mock.storage.get.return_value = storage_without_fraction

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.storage_local_storage_usage_percentage")
    assert state.state == STATE_UNKNOWN
