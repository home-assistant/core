"""Test bluesound integration."""

from pyblu.errors import PlayerUnreachableError

from homeassistant.components.bluesound import async_unload_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import PlayerMocks

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, setup_config_entry: None, config_entry: MockConfigEntry
) -> None:
    """Test a successful setup entry."""
    assert hass.states.get("media_player.player_name1111").state == "playing"
    assert config_entry.state is ConfigEntryState.LOADED

    assert await async_unload_entry(hass, config_entry)
    await hass.async_block_till_done()

    assert hass.states.get("media_player.player_name1111").state == "unavailable"
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_entry_while_player_is_offline(
    hass: HomeAssistant,
    setup_config_entry: None,
    config_entry: MockConfigEntry,
    player_mocks: PlayerMocks,
) -> None:
    """Test entries can be unloaded correctly while the player is offline."""
    player_mocks.player_data.player.status.side_effect = PlayerUnreachableError(
        "Player not reachable"
    )
    player_mocks.player_data.status_store.trigger()

    # this is only there to yield to the event loop once; there is nothing we can wait for
    await hass.async_block_till_done()

    assert await async_unload_entry(hass, config_entry)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.player_name1111").state == "unavailable"
