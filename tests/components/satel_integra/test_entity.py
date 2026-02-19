"""Test Satel Integra base entity."""

from unittest.mock import AsyncMock

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_controller_offline(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test availability for entities when controller is offline."""
    mock_satel.connected = False
    await setup_integration(hass, mock_config_entry_with_subentries)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry_with_subentries.entry_id
    )
    assert entity_entries
    for entity_entry in entity_entries:
        state = hass.states.get(entity_entry.entity_id)
        assert state, f"State not found for {entity_entry.entity_id}"
        assert state.state == STATE_UNAVAILABLE
