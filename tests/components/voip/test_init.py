"""Test VoIP init."""
from homeassistant.core import HomeAssistant

# socket_enabled,
# unused_udp_port_factory,


async def test_unload_entry(
    hass: HomeAssistant,
    config_entry,
    setup_voip,
) -> None:
    """Test adding/removing VoIP."""
    assert await hass.config_entries.async_unload(config_entry.entry_id)
