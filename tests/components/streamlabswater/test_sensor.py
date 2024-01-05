"""Tests for the Streamlabs Water sensor platform."""
from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.streamlabswater import setup_integration


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    streamlabswater: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.streamlabswater.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
        entity_entries = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )

        assert entity_entries
        for entity_entry in entity_entries:
            assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
            assert hass.states.get(entity_entry.entity_id) == snapshot(
                name=f"{entity_entry.entity_id}-state"
            )
