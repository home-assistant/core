"""Tests for the Bluesound Media Player platform."""

import asyncio
import dataclasses
from unittest.mock import call

from pyblu import PairedPlayer
from pyblu.errors import PlayerUnreachableError
import pytest

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import PlayerMocks


async def test_pause(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player pause."""
    await hass.services.async_call(
        "media_player",
        "media_pause",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.pause.assert_called_once()


async def test_play(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player play."""
    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.play.assert_called_once()


async def test_next_track(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player next track."""
    await hass.services.async_call(
        "media_player",
        "media_next_track",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.skip.assert_called_once()


async def test_previous_track(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player previous track."""
    await hass.services.async_call(
        "media_player",
        "media_previous_track",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.back.assert_called_once()


async def test_volume_set(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player volume set."""
    await hass.services.async_call(
        "media_player",
        "volume_set",
        {"entity_id": "media_player.player_name1111", "volume_level": 0.5},
        blocking=True,
    )

    player_mocks.player_data.player.volume.assert_called_once_with(level=50)


async def test_volume_mute(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player volume mute."""
    await hass.services.async_call(
        "media_player",
        "volume_mute",
        {"entity_id": "media_player.player_name1111", "is_volume_muted": True},
        blocking=True,
    )

    player_mocks.player_data.player.volume.assert_called_once_with(mute=True)


async def test_volume_up(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player volume up."""
    await hass.services.async_call(
        "media_player",
        "volume_up",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.volume.assert_called_once_with(level=11)


async def test_volume_down(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player volume down."""
    await hass.services.async_call(
        "media_player",
        "volume_down",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.volume.assert_called_once_with(level=9)


async def test_attributes_set(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player attributes set."""
    state = hass.states.get("media_player.player_name1111")
    assert state.state == "playing"
    assert state.attributes["volume_level"] == 0.1
    assert state.attributes["is_volume_muted"] is False
    assert state.attributes["media_content_type"] == "music"
    assert state.attributes["media_position"] == 2
    assert state.attributes["shuffle"] is False
    assert state.attributes["master"] is False
    assert state.attributes["friendly_name"] == "player-name1111"
    assert state.attributes["media_title"] == "song"
    assert state.attributes["media_artist"] == "artist"
    assert state.attributes["media_album_name"] == "album"


async def test_status_updated(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player status updated."""
    pre_state = hass.states.get("media_player.player_name1111")
    assert pre_state.state == "playing"
    assert pre_state.attributes["volume_level"] == 0.1

    status = player_mocks.player_data.status_store.get()
    status = dataclasses.replace(status, state="pause", volume=50, etag="changed")
    player_mocks.player_data.status_store.set(status)

    await asyncio.sleep(0)
    for _ in range(10):
        post_state = hass.states.get("media_player.player_name1111")
        if post_state.state == MediaPlayerState.PAUSED:
            break
        await asyncio.sleep(1)

    assert post_state.state == MediaPlayerState.PAUSED
    assert post_state.attributes["volume_level"] == 0.5


async def test_unavailable_when_offline(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test that the media player goes unavailable when the player is unreachable."""
    pre_state = hass.states.get("media_player.player_name1111")
    assert pre_state.state == "playing"

    player_mocks.player_data.player.status.side_effect = PlayerUnreachableError(
        "Player not reachable"
    )
    player_mocks.player_data.status_store.trigger()

    await asyncio.sleep(0)
    for _ in range(10):
        post_state = hass.states.get("media_player.player_name1111")
        if post_state.state == "unavailable":
            break
        await asyncio.sleep(1)

    assert post_state.state == "unavailable"


async def test_set_sleep_timer(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the set sleep timer action."""
    await hass.services.async_call(
        "bluesound",
        "set_sleep_timer",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.sleep_timer.assert_called_once()


async def test_clear_sleep_timer(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the clear sleep timer action."""

    player_mocks.player_data.player.sleep_timer.side_effect = [15, 30, 45, 60, 90, 0]

    await hass.services.async_call(
        "bluesound",
        "clear_sleep_timer",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.sleep_timer.assert_has_calls([call()] * 6)


async def test_join_cannot_join_to_self(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test that joining to self is not allowed."""
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            "bluesound",
            "join",
            {
                "entity_id": "media_player.player_name1111",
                "master": "media_player.player_name1111",
            },
            blocking=True,
        )

    assert str(exc.value) == "Cannot join player to itself"


async def test_join(
    hass: HomeAssistant,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the join action."""
    await hass.services.async_call(
        "bluesound",
        "join",
        {
            "entity_id": "media_player.player_name1111",
            "master": "media_player.player_name2222",
        },
        blocking=True,
    )

    player_mocks.player_data_secondary.player.add_slave.assert_called_once_with(
        "1.1.1.1", 11000
    )


async def test_unjoin(
    hass: HomeAssistant,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the unjoin action."""
    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_store.get(),
        master=PairedPlayer("2.2.2.2", 11000),
    )
    player_mocks.player_data.sync_status_store.set(updated_sync_status)

    # this might be flaky, but we do not have a way to wait for the master to be set
    await asyncio.sleep(0)

    await hass.services.async_call(
        "bluesound",
        "unjoin",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data_secondary.player.remove_slave.assert_called_once_with(
        "1.1.1.1", 11000
    )


async def test_attr_master(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player master."""
    attr_master = hass.states.get("media_player.player_name1111").attributes["master"]
    assert attr_master is False

    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_store.get(),
        slaves=[PairedPlayer("2.2.2.2", 11000)],
    )
    player_mocks.player_data.sync_status_store.set(updated_sync_status)

    for _ in range(10):
        attr_master = hass.states.get("media_player.player_name1111").attributes[
            "master"
        ]
        if attr_master:
            break
        await asyncio.sleep(1)

    assert attr_master is True


async def test_attr_bluesound_group(
    hass: HomeAssistant,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player grouping."""
    attr_bluesound_group = hass.states.get(
        "media_player.player_name1111"
    ).attributes.get("bluesound_group")
    assert attr_bluesound_group is None

    updated_status = dataclasses.replace(
        player_mocks.player_data.status_store.get(),
        group_name="player-name1111+player-name2222",
    )
    player_mocks.player_data.status_store.set(updated_status)

    for _ in range(10):
        attr_bluesound_group = hass.states.get(
            "media_player.player_name1111"
        ).attributes.get("bluesound_group")
        if attr_bluesound_group:
            break
        await asyncio.sleep(1)

    assert attr_bluesound_group == ["player-name1111", "player-name2222"]
