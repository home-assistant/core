"""Tests for the HDFury select platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SELECT]


async def test_select_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test HDFury select entities."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )
