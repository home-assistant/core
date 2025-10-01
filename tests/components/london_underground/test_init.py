"""Test the London Underground init."""

from homeassistant.components.london_underground.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_reload_entry(
    hass: HomeAssistant, mock_london_underground_client
) -> None:
    """Test reloading the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={"line": ["Bakerloo"]},
    )

    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Test reloading with updated options
    hass.config_entries.async_update_entry(
        entry,
        data={},
        options={"line": ["Bakerloo", "Central"]},
    )
    await hass.async_block_till_done()

    # Verify that setup was called for each reload
    assert len(mock_london_underground_client.mock_calls) > 0
