"""Tests for the compit component."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the Compit integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def snapshot_compit_entities(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Snapshot Compit entities."""
    entities = sorted(
        hass.states.async_all(platform),
        key=lambda state: state.entity_id,
    )
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        assert entity_entry and entity_entry == snapshot(
            name=f"{entity_entry.entity_id}-entry"
        )
        assert entity_state == snapshot(name=f"{entity_entry.entity_id}-state")
