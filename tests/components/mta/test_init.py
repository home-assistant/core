"""Test the MTA New York City Transit init."""

from unittest.mock import MagicMock

from homeassistant.components.mta.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_no_subentries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up an entry without subentries."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.config_entries.async_domains()


async def test_setup_entry_with_subway_subentry(
    hass: HomeAssistant,
    mock_config_entry_with_subway_subentry: MockConfigEntry,
    mock_subway_feed: MagicMock,
) -> None:
    """Test setting up an entry with a subway subentry."""
    mock_config_entry_with_subway_subentry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(
        mock_config_entry_with_subway_subentry.entry_id
    )
    await hass.async_block_till_done()

    assert mock_config_entry_with_subway_subentry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.config_entries.async_domains()

    # Verify coordinator was created for the subentry
    assert len(mock_config_entry_with_subway_subentry.runtime_data) == 1


async def test_setup_entry_with_bus_subentry(
    hass: HomeAssistant,
    mock_config_entry_with_bus_subentry: MockConfigEntry,
    mock_bus_feed: MagicMock,
) -> None:
    """Test setting up an entry with a bus subentry."""
    mock_config_entry_with_bus_subentry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(
        mock_config_entry_with_bus_subentry.entry_id
    )
    await hass.async_block_till_done()

    assert mock_config_entry_with_bus_subentry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.config_entries.async_domains()

    # Verify coordinator was created for the subentry
    assert len(mock_config_entry_with_bus_subentry.runtime_data) == 1


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry_with_subway_subentry: MockConfigEntry,
    mock_subway_feed: MagicMock,
) -> None:
    """Test unloading an entry."""
    mock_config_entry_with_subway_subentry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(
        mock_config_entry_with_subway_subentry.entry_id
    )
    await hass.async_block_till_done()

    assert mock_config_entry_with_subway_subentry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(
        mock_config_entry_with_subway_subentry.entry_id
    )
    await hass.async_block_till_done()

    assert mock_config_entry_with_subway_subentry.state is ConfigEntryState.NOT_LOADED
