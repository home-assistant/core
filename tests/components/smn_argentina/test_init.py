"""Test the SMN init module."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_setup_entry(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test successful setup of entry."""
    entry = await init_integration(hass)

    assert entry.state == ConfigEntryState.LOADED
    assert entry.runtime_data is not None


async def test_unload_entry(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED
