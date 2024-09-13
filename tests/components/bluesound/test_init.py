"""Test __init__."""

import asyncio

from pyblu.errors import PlayerUnreachableError

from homeassistant.components.bluesound import async_unload_entry
from homeassistant.core import HomeAssistant

from .conftest import PlayerMocks

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


async def test_unload_entry_while_offline(
    hass: HomeAssistant,
    setup_config_entry: None,
    config_entry: MockConfigEntry,
    player_mocks: PlayerMocks,
) -> None:
    """Test entries are unloaded correctly when the player is offline."""
    player_mocks.player_data.player.status.side_effect = PlayerUnreachableError(
        "Player not reachable"
    )
    player_mocks.player_data.status_store.trigger()

    # this needs to be here to make sure the player is offline
    await asyncio.sleep(0)

    assert await async_unload_entry(hass, config_entry)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.player_name1111").state == "unavailable"
