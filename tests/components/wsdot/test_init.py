"""The tests for the WSDOT platform."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_travel_sensor_setup_no_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_failed_travel_time: None,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the wsdot Travel Time sensor does not create an entry with a bad API key."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
