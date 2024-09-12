"""Test __init__."""

from homeassistant.components.bluesound import async_unload_entry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant, setup_config_entry: None) -> None:
    """Test a successful setup entry."""
    assert hass.states.get("media_player.player_name1111").state == "playing"


async def test_unload_entry(
    hass: HomeAssistant, setup_config_entry: None, config_entry: MockConfigEntry
) -> None:
    """Test entries are unloaded correctly."""
    assert await async_unload_entry(hass, config_entry)
    await hass.async_block_till_done()

    assert hass.states.get("media_player.player_name1111").state == "unavailable"
