"""Test bluesound integration."""

from pyblu.errors import PlayerUnreachableError

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

    assert await hass.config_entries.async_unload(config_entry.entry_id)
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
    player_mocks.player_data.status_long_polling_mock.trigger()

    # give the long polling loop a chance to update the state; this could be any async call
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("media_player.player_name1111").state == "unavailable"
    assert config_entry.state is ConfigEntryState.NOT_LOADED
