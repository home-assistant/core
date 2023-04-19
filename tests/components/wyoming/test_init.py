"""Test init."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_unload(
    hass: HomeAssistant, config_entry: ConfigEntry, init_wyoming_stt
) -> None:
    """Test unload."""
    assert await hass.config_entries.async_unload(config_entry.entry_id)
