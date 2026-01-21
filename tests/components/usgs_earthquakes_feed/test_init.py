"""Test the USGS Earthquakes Feed init."""

from unittest.mock import patch

from homeassistant.components.usgs_earthquakes_feed import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test setup entry."""
    config_entry.add_to_hass(hass)

    with (
        patch("aio_geojson_client.feed.GeoJsonFeed.update") as mock_feed_update,
    ):
        mock_feed_update.return_value = "OK", []
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert config_entry.entry_id in hass.config_entries.async_entries(DOMAIN)


async def test_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test unload entry."""
    config_entry.add_to_hass(hass)

    with (
        patch("aio_geojson_client.feed.GeoJsonFeed.update") as mock_feed_update,
    ):
        mock_feed_update.return_value = "OK", []
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
