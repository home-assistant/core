"""Test the London Underground init."""

from homeassistant.core import HomeAssistant


async def test_reload_entry(
    hass: HomeAssistant, mock_london_underground_client, mock_config_entry
) -> None:
    """Test reloading the config entry."""

    # Test reloading with updated options
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={},
        options={"line": ["Bakerloo", "Central"]},
    )
    await hass.async_block_till_done()

    # Verify that setup was called for each reload
    assert len(mock_london_underground_client.mock_calls) > 0
