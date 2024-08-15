"""Test the wmspro diagnostics."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_test: AsyncMock,
    mock_dest_refresh: AsyncMock,
) -> None:
    """Test that a config entry can be loaded with DeviceConfig."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_test.mock_calls) == 1
    assert len(mock_dest_refresh.mock_calls) == 2

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert result["control"]["_control"] == "http://webcontrol/commonCommand"
    assert result["control"]["_host"] == "webcontrol"
    assert len(result["control"]["dests"]) == len(result["dests"])
    assert len(result["control"]["rooms"]) == len(result["rooms"])
    assert len(result["control"]["scenes"]) == len(result["scenes"])
    assert len(result["dests"]) == 2
    assert len(result["rooms"]) == 1
    assert len(result["scenes"]) == 1
