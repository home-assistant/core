"""Test Green Planet Energy setup."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_entry(hass: HomeAssistant, mock_api, mock_config_entry) -> None:
    """Test setting up config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant, mock_api, mock_config_entry) -> None:
    """Test unloading config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
