"""Snapshot tests for the Atomberg entities."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.atomberg import PLATFORMS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.mark.parametrize("platform", PLATFORMS)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    platform: Platform,
) -> None:
    """Test all entities of a platform."""
    with patch("homeassistant.components.atomberg.PLATFORMS", [platform]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
