"""Test Discogs integration init."""

from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test successful setup of config entry."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.discogs.sensor.discogs_client.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test unloading a config entry."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.discogs.sensor.discogs_client.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
