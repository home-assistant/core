"""Entity base tests for iAquaLink."""

from __future__ import annotations

from iaqualink.client import AqualinkClient
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities are created by setup_integration."""
    await setup_integration(hass, config_entry, client)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        state = hass.states.get(entity_entry.entity_id)
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")
