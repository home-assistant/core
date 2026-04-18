"""Test Satel Integra base entity."""

from unittest.mock import AsyncMock

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_availability_status_on_connection_change(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity availability changes based on controller connection status."""
    await setup_integration(hass, mock_config_entry_with_subentries)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry_with_subentries.entry_id
    )

    # Get all registered connection status callbacks (one per coordinator)
    connection_status_callbacks = [
        call[0][0] for call in mock_satel.add_connection_status_callback.call_args_list
    ]
    assert connection_status_callbacks

    # Verify entities are available when controller is connected
    for entity_entry in entity_entries:
        state = hass.states.get(entity_entry.entity_id)
        assert state, f"State not found for {entity_entry.entity_id}"
        assert state.state != STATE_UNAVAILABLE

    # Simulate controller going offline and trigger all connection callbacks
    mock_satel.connected = False
    for callback in connection_status_callbacks:
        callback()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify all entities become unavailable
    for entity_entry in entity_entries:
        state = hass.states.get(entity_entry.entity_id)
        assert state, f"State not found for {entity_entry.entity_id}"
        assert state.state == STATE_UNAVAILABLE

    # Simulate controller coming back online and trigger all connection callbacks
    mock_satel.connected = True
    for callback in connection_status_callbacks:
        callback()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify entities are available again
    for entity_entry in entity_entries:
        state = hass.states.get(entity_entry.entity_id)
        assert state, f"State not found for {entity_entry.entity_id}"
        assert state.state != STATE_UNAVAILABLE
