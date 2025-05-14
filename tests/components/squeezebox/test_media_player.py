"""Tests for the squeezebox media player component."""

from datetime import timedelta
import json
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_JOIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_UNJOIN,
    MediaPlayerEnqueue,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.components.squeezebox.const import (
    ATTR_ANNOUNCE_TIMEOUT,
    ATTR_ANNOUNCE_VOLUME,
    DISCOVERY_INTERVAL,
    DOMAIN,
    PLAYER_UPDATE_INTERVAL,
    SENSOR_UPDATE_INTERVAL,
)
from homeassistant.components.squeezebox.media_player import (
    ATTR_PARAMETERS,
    SERVICE_CALL_METHOD,
    SERVICE_CALL_QUERY,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util.dt import utcnow

from .conftest import FAKE_VALID_ITEM_ID, TEST_MAC, TEST_VOLUME_STEP

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_device_registry(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    configured_player: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test squeezebox device registered in the device registry."""
    reg_device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_MAC[0])})
    assert reg_device is not None
    assert reg_device == snapshot


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    configured_player: MagicMock,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
) -> None:
    """Test squeezebox media_player entity registered in the entity registry."""
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_squeezebox_player_rediscovery(
    hass: HomeAssistant, configured_player: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test rediscovery of a squeezebox player."""

    assert hass.states.get("media_player.test_player").state == MediaPlayerState.IDLE

    # Make the player appear unavailable
    configured_player.connected = False
    freezer.tick(timedelta(seconds=PLAYER_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.test_player").state == STATE_UNAVAILABLE

    # Make the player available again
    configured_player.connected = True
    freezer.tick(timedelta(seconds=DISCOVERY_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=PLAYER_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.IDLE


async def test_squeezebox_turn_on(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test turn on service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_set_power.assert_called_once_with(True)


async def test_squeezebox_turn_off(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test turn off service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_set_power.assert_called_once_with(False)


async def test_squeezebox_state(
    hass: HomeAssistant, configured_player: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test determining the MediaPlayerState."""

    configured_player.power = True
    configured_player.mode = "stop"
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.IDLE

    configured_player.mode = "play"
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.PLAYING

    configured_player.mode = "pause"
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.PAUSED

    configured_player.power = False
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.OFF


async def test_squeezebox_volume_up(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test volume up service call."""
    configured_player.volume = 50
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_set_volume.assert_called_once_with(
        str(configured_player.volume + TEST_VOLUME_STEP)
    )


async def test_squeezebox_volume_down(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test volume down service call."""
    configured_player.volume = 50
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_set_volume.assert_called_once_with(
        str(configured_player.volume - TEST_VOLUME_STEP)
    )


async def test_squeezebox_volume_set(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test volume set service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    configured_player.async_set_volume.assert_called_once_with("50")


async def test_squeezebox_volume_property(
    hass: HomeAssistant, configured_player: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test volume property."""

    configured_player.volume = 50
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.5
    )

    configured_player.volume = None
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        ATTR_MEDIA_VOLUME_LEVEL
        not in hass.states.get("media_player.test_player").attributes
    )


async def test_squeezebox_mute(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test mute service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    configured_player.async_set_muting.assert_called_once_with(True)


async def test_squeezebox_unmute(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test unmute service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )
    configured_player.async_set_muting.assert_called_once_with(False)


async def test_squeezebox_mute_property(
    hass: HomeAssistant, configured_player: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the mute property."""

    configured_player.muting = True
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_VOLUME_MUTED]
        is True
    )

    configured_player.muting = False
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_VOLUME_MUTED]
        is False
    )


async def test_squeezebox_repeat_mode(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test set repeat mode service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_REPEAT: RepeatMode.ALL,
        },
        blocking=True,
    )
    configured_player.async_set_repeat.assert_called_once_with("playlist")

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_REPEAT: RepeatMode.ONE,
        },
        blocking=True,
    )
    configured_player.async_set_repeat.assert_called_with("song")

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_REPEAT: RepeatMode.OFF,
        },
        blocking=True,
    )
    configured_player.async_set_repeat.assert_called_with("none")


async def test_squeezebox_repeat_mode_property(
    hass: HomeAssistant, configured_player: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the repeat mode property."""
    configured_player.repeat = "playlist"
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_REPEAT]
        == RepeatMode.ALL
    )

    configured_player.repeat = "song"
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_REPEAT]
        == RepeatMode.ONE
    )

    configured_player.repeat = "none"
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_REPEAT]
        == RepeatMode.OFF
    )


async def test_squeezebox_shuffle(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test set shuffle service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_SHUFFLE: True,
        },
        blocking=True,
    )
    configured_player.async_set_shuffle.assert_called_once_with("song")

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_SHUFFLE: False,
        },
        blocking=True,
    )
    configured_player.async_set_shuffle.assert_called_with("none")
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_SHUFFLE]
        is False
    )


async def test_squeezebox_shuffle_property(
    hass: HomeAssistant, configured_player: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the shuffle property."""

    configured_player.shuffle = "song"
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_SHUFFLE]
        is True
    )

    configured_player.shuffle = "none"
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_SHUFFLE]
        is False
    )


async def test_squeezebox_play(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test play service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_play.assert_called_once()


async def test_squeezebox_play_media_with_announce(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test play service call with announce."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
            ATTR_MEDIA_ANNOUNCE: True,
        },
        blocking=True,
    )
    configured_player.async_load_url.assert_called_once_with(
        FAKE_VALID_ITEM_ID, "announce"
    )


@pytest.mark.parametrize(
    "announce_volume",
    ["0.2", 0.2],
)
async def test_squeezebox_play_media_with_announce_volume(
    hass: HomeAssistant, configured_player: MagicMock, announce_volume: str | int
) -> None:
    """Test play service call with announce."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
            ATTR_MEDIA_ANNOUNCE: True,
            ATTR_MEDIA_EXTRA: {ATTR_ANNOUNCE_VOLUME: announce_volume},
        },
        blocking=True,
    )
    configured_player.set_announce_volume.assert_called_once_with(20)
    configured_player.async_load_url.assert_called_once_with(
        FAKE_VALID_ITEM_ID, "announce"
    )


@pytest.mark.parametrize("announce_volume", ["1.1", 1.1, "text", "-1", -1, 0, "0"])
async def test_squeezebox_play_media_with_announce_volume_invalid(
    hass: HomeAssistant, configured_player: MagicMock, announce_volume: str | int
) -> None:
    """Test play service call with announce and volume zero."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
                ATTR_MEDIA_ANNOUNCE: True,
                ATTR_MEDIA_EXTRA: {ATTR_ANNOUNCE_VOLUME: announce_volume},
            },
            blocking=True,
        )


@pytest.mark.parametrize("announce_timeout", ["-1", "text", -1, 0, "0"])
async def test_squeezebox_play_media_with_announce_timeout_invalid(
    hass: HomeAssistant, configured_player: MagicMock, announce_timeout: str | int
) -> None:
    """Test play service call with announce and invalid timeout."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
                ATTR_MEDIA_ANNOUNCE: True,
                ATTR_MEDIA_EXTRA: {ATTR_ANNOUNCE_TIMEOUT: announce_timeout},
            },
            blocking=True,
        )


@pytest.mark.parametrize("announce_timeout", ["100", 100])
async def test_squeezebox_play_media_with_announce_timeout(
    hass: HomeAssistant, configured_player: MagicMock, announce_timeout: str | int
) -> None:
    """Test play service call with announce."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
            ATTR_MEDIA_ANNOUNCE: True,
            ATTR_MEDIA_EXTRA: {ATTR_ANNOUNCE_TIMEOUT: announce_timeout},
        },
        blocking=True,
    )
    configured_player.set_announce_timeout.assert_called_once_with(100)
    configured_player.async_load_url.assert_called_once_with(
        FAKE_VALID_ITEM_ID, "announce"
    )


async def test_squeezebox_play_pause(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test play/pause service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY_PAUSE,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_toggle_pause.assert_called_once()


async def test_squeezebox_pause(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test pause service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_pause.assert_called_once()


async def test_squeezebox_seek(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test seek service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
        },
        blocking=True,
    )
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_SEEK,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_SEEK_POSITION: 100,
        },
        blocking=True,
    )
    configured_player.async_time.assert_called_once_with(100)


async def test_squeezebox_stop(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test stop service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_stop.assert_called_once()


async def test_squeezebox_load_playlist(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test load a playlist."""
    # load a playlist by number
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
        },
        blocking=True,
    )
    assert configured_player.async_load_playlist.call_count == 1

    # load a list of urls
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: json.dumps(
                {
                    "urls": [
                        {"url": FAKE_VALID_ITEM_ID},
                        {"url": FAKE_VALID_ITEM_ID + "_2"},
                    ],
                    "index": "0",
                }
            ),
            ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
        },
        blocking=True,
    )
    assert configured_player.async_load_playlist.call_count == 2

    # clear the playlist
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_CLEAR_PLAYLIST,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_clear_playlist.assert_called_once()


async def test_squeezebox_enqueue(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test the various enqueue service calls."""

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.ADD,
        },
        blocking=True,
    )
    configured_player.async_load_url.assert_called_once_with(FAKE_VALID_ITEM_ID, "add")

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.NEXT,
        },
        blocking=True,
    )
    configured_player.async_load_url.assert_called_with(FAKE_VALID_ITEM_ID, "insert")

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.PLAY,
        },
        blocking=True,
    )
    configured_player.async_load_url.assert_called_with(FAKE_VALID_ITEM_ID, "play_now")


async def test_squeezebox_skip_tracks(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test track skipping service calls."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
        },
        blocking=True,
    )
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_index.assert_called_once_with("+1")

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_index.assert_called_with("-1")


async def test_squeezebox_call_query(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test query service call."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CALL_QUERY,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_COMMAND: "test_command",
            ATTR_PARAMETERS: ["param1", "param2"],
        },
        blocking=True,
    )
    configured_player.async_query.assert_called_once_with(
        "test_command", "param1", "param2"
    )


async def test_squeezebox_call_method(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test method call service call."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CALL_METHOD,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_COMMAND: "test_command",
            ATTR_PARAMETERS: ["param1", "param2"],
        },
        blocking=True,
    )
    configured_player.async_query.assert_called_once_with(
        "test_command", "param1", "param2"
    )


async def test_squeezebox_invalid_state(
    hass: HomeAssistant, configured_player: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test handling an unexpected state from pysqueezebox."""
    configured_player.mode = "invalid"
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.test_player").state == STATE_UNKNOWN


async def test_squeezebox_server_discovery(
    hass: HomeAssistant,
    lms: MagicMock,
    lms_factory: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test discovery of a squeezebox server."""

    async def mock_async_discover(callback):
        """Mock the async_discover function of pysqueezebox."""
        return callback(lms_factory(2))

    lms.async_prepared_status.return_value = {}

    with (
        patch(
            "homeassistant.components.squeezebox.Server",
            return_value=lms,
        ),
        patch(
            "homeassistant.components.squeezebox.media_player.async_discover",
            mock_async_discover,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        # how do we check that a config flow started?


async def test_squeezebox_join(hass: HomeAssistant, configured_players: list) -> None:
    """Test joining a squeezebox player."""

    # join a valid player
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_GROUP_MEMBERS: ["media_player.test_player_2"],
        },
        blocking=True,
    )
    configured_players[0].async_sync.assert_called_once_with(
        configured_players[1].player_id
    )

    # try to join an invalid player
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_GROUP_MEMBERS: ["media_player.invalid"],
            },
            blocking=True,
        )


async def test_squeezebox_unjoin(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test unjoining a squeezebox player."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_UNJOIN,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_unsync.assert_called_once()


async def test_squeezebox_media_content_properties(
    hass: HomeAssistant,
    configured_player: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test media_content_id and media_content_type properties."""
    playlist_urls = [
        {"url": "test_title"},
        {"url": "test_title_2"},
    ]
    configured_player.current_index = 0
    configured_player.playlist = playlist_urls
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.test_player").attributes[
        ATTR_MEDIA_CONTENT_ID
    ] == json.dumps({"index": 0, "urls": playlist_urls})
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_CONTENT_TYPE]
        == MediaType.PLAYLIST
    )

    configured_player.url = "test_url"
    configured_player.playlist = [{"url": "test_url"}]
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_CONTENT_ID]
        == "test_url"
    )
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_CONTENT_TYPE]
        == MediaType.MUSIC
    )

    configured_player.playlist = None
    configured_player.url = None
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        ATTR_MEDIA_CONTENT_ID
        not in hass.states.get("media_player.test_player").attributes
    )
    assert (
        ATTR_MEDIA_CONTENT_TYPE
        not in hass.states.get("media_player.test_player").attributes
    )


async def test_squeezebox_media_position_property(
    hass: HomeAssistant, configured_player: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test media_position property."""
    configured_player.time = 100
    configured_player.async_update = AsyncMock(
        side_effect=lambda: setattr(configured_player, "time", 105)
    )
    last_update = utcnow()
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_POSITION]
        == 105
    )
    assert (
        (
            hass.states.get("media_player.test_player").attributes[
                ATTR_MEDIA_POSITION_UPDATED_AT
            ]
        )
        > last_update
    )
