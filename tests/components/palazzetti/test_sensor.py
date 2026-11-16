"""Tests for the Palazzetti sensor platform."""

from unittest.mock import AsyncMock, patch

from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.palazzetti.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

        disabled_entries = [
            entry
            for entry in er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
            if entry.disabled_by
        ]
        assert disabled_entries
        assert all(
            entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
            for entry in disabled_entries
        )
        for entry in disabled_entries:
            entity_registry.async_update_entity(entry.entity_id, disabled_by=None)

        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )
