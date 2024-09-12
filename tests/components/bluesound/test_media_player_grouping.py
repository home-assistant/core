"""Tests for the Bluesound Media Player grouping."""

import asyncio
import dataclasses

from pyblu import PairedPlayer, Player, SyncStatus

from homeassistant.core import HomeAssistant

from .conftest import PlayerMocks
from .utils import ValueStore


async def test_master(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player master."""
    attr_master = hass.states.get("media_player.player_name1111").attributes["master"]
    assert attr_master is False

    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_store.get(), slaves=[PairedPlayer("2.2.2.2", 11000)]
    )
    player_mocks.player_data.sync_status_store.set(updated_sync_status)

    for _ in range(10):
        attr_master = hass.states.get("media_player.player_name1111").attributes["master"]
        if attr_master:
            break
        await asyncio.sleep(1)

    assert attr_master is True

async def test_bluesound_group(
    hass: HomeAssistant,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player grouping."""
    attr_bluesound_group = hass.states.get("media_player.player_name1111").attributes.get("bluesound_group")
    assert attr_bluesound_group is None

    updated_status = dataclasses.replace(
        player_mocks.player_data.status_store.get(), group_name="player-name1111+player-name2222"
    )
    player_mocks.player_data.status_store.set(updated_status)

    for _ in range(10):
        attr_bluesound_group = hass.states.get("media_player.player_name1111").attributes.get("bluesound_group")
        if attr_bluesound_group:
            break
        await asyncio.sleep(1)

    assert attr_bluesound_group == ["player-name1111", "player-name2222"]


