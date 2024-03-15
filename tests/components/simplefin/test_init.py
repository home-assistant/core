"""Test config flow."""


from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_init(
    hass: HomeAssistant,
    mock_access_url,
    mock_config_entry: MockConfigEntry,
    mock_get_financial_data,
):
    """Test the init method."""
    mock_config_entry.add_to_hass(hass)

    assert mock_config_entry.unique_id == mock_access_url
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state == ConfigEntryState.LOADED
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
