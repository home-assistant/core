"""Test SensorPush Cloud sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_helper: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test we can read sensors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
