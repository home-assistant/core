"""Test Snooz configuration."""
from __future__ import annotations

from pysnooz import commands

from homeassistant.core import HomeAssistant

from . import SnoozFixture


async def test_removing_entry_cleans_up_connections(
    hass: HomeAssistant, mock_snooz: SnoozFixture
):
    """Tests setup and removal of a config entry, ensuring connections are cleaned up."""
    # create a connection
    await mock_snooz.data.device.async_execute_command(commands.turn_on())
    assert mock_snooz.data.device.is_connected

    await hass.config_entries.async_remove(mock_snooz.entry.entry_id)
    await hass.async_block_till_done()

    assert not mock_snooz.data.device.is_connected


async def test_reloading_entry_cleans_up_connections(
    hass: HomeAssistant, mock_snooz: SnoozFixture
):
    """Test reloading an entry disconnects any existing connections."""
    # create a connection
    await mock_snooz.data.device.async_execute_command(commands.turn_on())
    assert mock_snooz.data.device.is_connected

    await hass.config_entries.async_reload(mock_snooz.entry.entry_id)
    await hass.async_block_till_done()

    assert not mock_snooz.data.device.is_connected
