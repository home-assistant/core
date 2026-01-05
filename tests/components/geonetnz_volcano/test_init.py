"""Define tests for the GeoNet NZ Volcano general setup."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant


async def test_component_unload_config_entry(hass: HomeAssistant, config_entry) -> None:
    """Test that loading and unloading of a config entry works."""
    config_entry.add_to_hass(hass)
    with patch(
        "aio_geojson_geonetnz_volcano.GeonetnzVolcanoFeedManager.update",
        new_callable=AsyncMock,
    ) as mock_feed_manager_update:
        # Load config entry.
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_feed_manager_update.call_count == 1

        # Unload config entry.
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
