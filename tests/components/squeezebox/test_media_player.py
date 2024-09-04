"""Tests for the squeezebox media player component."""

from unittest.mock import MagicMock

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.components.squeezebox.const import DOMAIN
from homeassistant.const import (
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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceRegistry

from .conftest import TEST_MAC, TEST_PLAYER_NAME


async def test_device_registry(
    hass: HomeAssistant, device_registry: DeviceRegistry, configured_player: MagicMock
) -> None:
    """Test squeezebox device registered in the device registry."""
    reg_device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_MAC)})
    assert reg_device is not None
    assert reg_device.connections == {
        (CONNECTION_NETWORK_MAC, TEST_MAC),
    }
    assert reg_device.name == TEST_PLAYER_NAME
    assert reg_device.suggested_area is None


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
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.IDLE


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
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.OFF


async def test_squeezebox_volume_up(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test volume up service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_set_volume.assert_called_once_with("+5")
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.15
    )


async def test_squeezebox_volume_down(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test volume down service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    configured_player.async_set_volume.assert_called_once_with("-5")
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.05
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
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.5
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
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_VOLUME_MUTED]
        is True
    )


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
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_REPEAT]
        == RepeatMode.ALL
    )
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
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_REPEAT]
        == RepeatMode.ONE
    )
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
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_SHUFFLE]
        is True
    )
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
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.PLAYING


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
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.PLAYING
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY_PAUSE,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert configured_player.async_toggle_pause.call_count == 2
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.PAUSED


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
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.PAUSED


async def test_squeezebox_seek(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test seek service call."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: "1234",
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
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_POSITION]
        == 100
    )


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
    assert hass.states.get("media_player.test_player").state == MediaPlayerState.IDLE


async def test_squeezebox_playlists(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test load a playlist."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: "1234",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
        },
        blocking=True,
    )
    assert len(
        hass.states.get("media_player.test_player").attributes[ATTR_MEDIA_CONTENT_ID]
    )


async def test_squeezebox_skip_tracks(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test track skipping service calls."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: "1234",
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
