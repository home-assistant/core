"""Test VoIP init."""
from homeassistant.core import HomeAssistant


async def test_unload_entry(
    hass: HomeAssistant,
    config_entry,
    setup_voip,
) -> None:
    """Test adding/removing VoIP."""
    assert await hass.config_entries.async_unload(config_entry.entry_id)
