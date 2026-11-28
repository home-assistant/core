"""The tests for the Media group platform."""

import asyncio
from logging import ERROR
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from pytest_homeassistant.common import setup_test_component_platform

from homeassistant.components.group import DOMAIN
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_DOMAIN,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerService,
    MediaPlayerServiceArgument,
    MediaPlayerState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform, entity_registry as er
from homeassistant.setup import async_setup_component


@pytest.fixture(name="mock_media_seek")
def media_player_media_seek_fixture():
    """Mock demo YouTube player media seek."""
    with patch(
        "homeassistant.components.demo.media_player.DemoYoutubePlayer.media_seek",
        autospec=True,
    ) as seek:
        yield seek


async def test_default_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test media group default state."""
    hass.states.async_set("media_player.player_1", "on")
    await async_setup_component(
        hass,
        MEDIA_DOMAIN,
        {
            MEDIA_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["media_player.player_1", "media_player.player_2"],
                "name": "Media group",
                "unique_id": "unique_identifier",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("media_player.media_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "media_player.player_1",
        "media_player.player_2",
    ]

    entry = entity_registry.async_get("media_player.media_group")
    assert entry
    assert entry.unique_id == "unique_identifier"


async def test_state_reporting(hass: HomeAssistant) -> None:
    """Test the state reporting.

    The group state is unavailable if all group members are unavailable.
    Otherwise, the group state is unknown if all group members are unknown.
    Otherwise, the group state is buffering if all group members are buffering.
    Otherwise, the group state is idle if all group members are idle.
    Otherwise, the group state is paused if all group members are paused.
    Otherwise, the group state is playing if all group members are playing.
    Otherwise, the group state is on if at least one group member is
    not off, unavailable or unknown.
    Otherwise, the group state is off.
    """
    await async_setup_component(
        hass,
        MEDIA_DOMAIN,
        {
            MEDIA_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["media_player.player_1", "media_player.player_2"],
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Initial state with no group member in the state machine -> unavailable
    assert hass.states.get("media_player.media_group").state == STATE_UNAVAILABLE

    # All group members unavailable -> unavailable
    hass.states.async_set("media_player.player_1", STATE_UNAVAILABLE)
    hass.states.async_set("media_player.player_2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.media_group").state == STATE_UNAVAILABLE

    # The group state is unknown if all group members are unknown or unavailable.
    for state_1 in (
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        hass.states.async_set("media_player.player_1", state_1)
        hass.states.async_set("media_player.player_2", STATE_UNKNOWN)
        await hass.async_block_till_done()
        assert hass.states.get("media_player.media_group").state == STATE_UNKNOWN

    # All group members buffering -> buffering
    # All group members idle -> idle
    # All group members paused -> paused
    # All group members playing -> playing
    # All group members unavailable -> unavailable
    # All group members unknown -> unknown
    for state in (
        STATE_BUFFERING,
        STATE_IDLE,
        STATE_PAUSED,
        STATE_PLAYING,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        hass.states.async_set("media_player.player_1", state)
        hass.states.async_set("media_player.player_2", state)
        await hass.async_block_till_done()
        assert hass.states.get("media_player.media_group").state == state

    # At least one member not off, unavailable or unknown -> on
    for state_1 in (STATE_BUFFERING, STATE_IDLE, STATE_ON, STATE_PAUSED, STATE_PLAYING):
        for state_2 in (STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN):
            hass.states.async_set("media_player.player_1", state_1)
            hass.states.async_set("media_player.player_2", state_2)
            await hass.async_block_till_done()
            assert hass.states.get("media_player.media_group").state == STATE_ON

    # Otherwise off
    for state_1 in (STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN):
        hass.states.async_set("media_player.player_1", state_1)
        hass.states.async_set("media_player.player_2", STATE_OFF)
        await hass.async_block_till_done()
        assert hass.states.get("media_player.media_group").state == STATE_OFF

    # All group members in same invalid state -> unknown
    hass.states.async_set("media_player.player_1", "invalid_state")
    hass.states.async_set("media_player.player_2", "invalid_state")
    await hass.async_block_till_done()
    assert hass.states.get("media_player.media_group").state == STATE_UNKNOWN

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove("media_player.player_1")
    hass.states.async_remove("media_player.player_2")
    await hass.async_block_till_done()
    assert hass.states.get("media_player.media_group").state == STATE_UNAVAILABLE


async def test_supported_features(hass: HomeAssistant) -> None:
    """Test supported features reporting."""
    pause_play_stop = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
    )
    play_media = (
        MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
        | MediaPlayerEntityFeature.MEDIA_ENQUEUE
    )
    volume = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    await async_setup_component(
        hass,
        MEDIA_DOMAIN,
        {
            MEDIA_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["media_player.player_1", "media_player.player_2"],
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set(
        "media_player.player_1", STATE_ON, {ATTR_SUPPORTED_FEATURES: 0}
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.media_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    hass.states.async_set(
        "media_player.player_1",
        STATE_ON,
        {ATTR_SUPPORTED_FEATURES: pause_play_stop},
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.media_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == pause_play_stop

    hass.states.async_set(
        "media_player.player_2",
        STATE_OFF,
        {ATTR_SUPPORTED_FEATURES: play_media | volume},
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.media_group")
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == pause_play_stop | play_media | volume
    )

    hass.states.async_set(
        "media_player.player_2", STATE_OFF, {ATTR_SUPPORTED_FEATURES: play_media}
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.media_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == pause_play_stop | play_media


async def test_service_calls(hass: HomeAssistant, mock_media_seek: Mock) -> None:
    """Test service calls."""
    await async_setup_component(
        hass,
        MEDIA_DOMAIN,
        {
            MEDIA_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "media_player.bedroom",
                        "media_player.kitchen",
                        "media_player.living_room",
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("media_player.media_group").state == STATE_PLAYING
    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.TURN_OFF,
        {TargetKey.ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_OFF
    assert hass.states.get("media_player.kitchen").state == STATE_OFF
    assert hass.states.get("media_player.living_room").state == STATE_OFF

    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.TURN_ON,
        {TargetKey.ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_PLAYING
    assert hass.states.get("media_player.kitchen").state == STATE_PLAYING
    assert hass.states.get("media_player.living_room").state == STATE_PLAYING

    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.MEDIA_PAUSE,
        {TargetKey.ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_PAUSED
    assert hass.states.get("media_player.kitchen").state == STATE_PAUSED
    assert hass.states.get("media_player.living_room").state == STATE_PAUSED

    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.MEDIA_PLAY,
        {TargetKey.ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_PLAYING
    assert hass.states.get("media_player.kitchen").state == STATE_PLAYING
    assert hass.states.get("media_player.living_room").state == STATE_PLAYING

    # ATTR_MEDIA_TRACK is not supported by bedroom and living_room players
    assert hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_TRACK] == 1
    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.MEDIA_NEXT_TRACK,
        {TargetKey.ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_TRACK] == 2

    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.MEDIA_PREVIOUS_TRACK,
        {TargetKey.ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_TRACK] == 1

    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.PLAY_MEDIA,
        {
            TargetKey.ENTITY_ID: "media_player.media_group",
            MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE: "some_type",
            MediaPlayerServiceArgument.MEDIA_CONTENT_ID: "some_id",
        },
    )
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.bedroom").attributes[ATTR_MEDIA_CONTENT_ID]
        == "some_id"
    )
    # media_player.kitchen is skipped because it always returns "bounzz-1"
    assert (
        hass.states.get("media_player.living_room").attributes[ATTR_MEDIA_CONTENT_ID]
        == "some_id"
    )

    state = hass.states.get("media_player.media_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & MediaPlayerEntityFeature.SEEK
    assert not mock_media_seek.called

    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.MEDIA_SEEK,
        {
            TargetKey.ENTITY_ID: "media_player.media_group",
            MediaPlayerServiceArgument.SEEK_POSITION: 100,
        },
    )
    await hass.async_block_till_done()
    assert mock_media_seek.called

    assert (
        hass.states.get("media_player.bedroom").attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1
    )
    assert (
        hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1
    )
    assert (
        hass.states.get("media_player.living_room").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 1
    )
    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.VOLUME_SET,
        {
            TargetKey.ENTITY_ID: "media_player.media_group",
            MediaPlayerServiceArgument.VOLUME_LEVEL: 0.5,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.bedroom").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.5
    )
    assert (
        hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.5
    )
    assert (
        hass.states.get("media_player.living_room").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.5
    )

    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.VOLUME_UP,
        {TargetKey.ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.bedroom").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.6
    )
    assert (
        hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.6
    )
    assert (
        hass.states.get("media_player.living_room").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.6
    )

    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.VOLUME_DOWN,
        {TargetKey.ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.bedroom").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.5
    )
    assert (
        hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.5
    )
    assert (
        hass.states.get("media_player.living_room").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == 0.5
    )

    assert (
        hass.states.get("media_player.bedroom").attributes[ATTR_MEDIA_VOLUME_MUTED]
        is False
    )
    assert (
        hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_VOLUME_MUTED]
        is False
    )
    assert (
        hass.states.get("media_player.living_room").attributes[ATTR_MEDIA_VOLUME_MUTED]
        is False
    )
    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.VOLUME_MUTE,
        {
            TargetKey.ENTITY_ID: "media_player.media_group",
            MediaPlayerServiceArgument.IS_VOLUME_MUTED: True,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.bedroom").attributes[ATTR_MEDIA_VOLUME_MUTED]
        is True
    )
    assert (
        hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_VOLUME_MUTED]
        is True
    )
    assert (
        hass.states.get("media_player.living_room").attributes[ATTR_MEDIA_VOLUME_MUTED]
        is True
    )

    assert (
        hass.states.get("media_player.bedroom").attributes[ATTR_MEDIA_SHUFFLE] is False
    )
    assert (
        hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_SHUFFLE] is False
    )
    assert (
        hass.states.get("media_player.living_room").attributes[ATTR_MEDIA_SHUFFLE]
        is False
    )
    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.SHUFFLE_SET,
        {
            TargetKey.ENTITY_ID: "media_player.media_group",
            MediaPlayerServiceArgument.SHUFFLE: True,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert (
        hass.states.get("media_player.bedroom").attributes[ATTR_MEDIA_SHUFFLE] is True
    )
    assert (
        hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_SHUFFLE] is True
    )
    assert (
        hass.states.get("media_player.living_room").attributes[ATTR_MEDIA_SHUFFLE]
        is True
    )

    assert hass.states.get("media_player.bedroom").state == STATE_PLAYING
    assert hass.states.get("media_player.kitchen").state == STATE_PLAYING
    assert hass.states.get("media_player.living_room").state == STATE_PLAYING
    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.CLEAR_PLAYLIST,
        {TargetKey.ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    # SERVICE_CLEAR_PLAYLIST is not supported by bedroom and living_room players
    assert hass.states.get("media_player.kitchen").state == STATE_OFF

    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.MEDIA_PLAY,
        {TargetKey.ENTITY_ID: "media_player.kitchen"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_PLAYING
    assert hass.states.get("media_player.kitchen").state == STATE_PLAYING
    assert hass.states.get("media_player.living_room").state == STATE_PLAYING
    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.MEDIA_STOP,
        {TargetKey.ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_OFF
    assert hass.states.get("media_player.kitchen").state == STATE_OFF
    assert hass.states.get("media_player.living_room").state == STATE_OFF


async def test_nested_group(hass: HomeAssistant) -> None:
    """Test nested media group."""
    await async_setup_component(
        hass,
        MEDIA_DOMAIN,
        {
            MEDIA_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": ["media_player.group_1"],
                    "name": "Nested Group",
                },
                {
                    "platform": DOMAIN,
                    "entities": ["media_player.bedroom", "media_player.kitchen"],
                    "name": "Group 1",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("media_player.group_1")
    assert state is not None
    assert state.state == STATE_PLAYING
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "media_player.bedroom",
        "media_player.kitchen",
    ]

    state = hass.states.get("media_player.nested_group")
    assert state is not None
    assert state.state == STATE_PLAYING
    assert state.attributes.get(ATTR_ENTITY_ID) == ["media_player.group_1"]

    # Test controlling the nested group
    async with asyncio.timeout(0.5):
        await hass.services.async_call(
            MEDIA_DOMAIN,
            MediaPlayerService.TURN_OFF,
            {TargetKey.ENTITY_ID: "media_player.group_1"},
            blocking=True,
        )

    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_OFF
    assert hass.states.get("media_player.kitchen").state == STATE_OFF
    assert hass.states.get("media_player.group_1").state == STATE_OFF
    assert hass.states.get("media_player.nested_group").state == STATE_OFF


async def test_service_play_media_kwargs(hass: HomeAssistant) -> None:
    """Test that kwargs get passed through on play_media service call."""
    await async_setup_component(
        hass,
        MEDIA_DOMAIN,
        {
            MEDIA_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "media_player.bedroom",
                        "media_player.living_room",
                    ],
                },
            ]
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    platform = entity_platform.async_get_platforms(hass, "media_player")[0]
    mp_bedroom = platform.domain_entities["media_player.bedroom"]
    mp_bedroom.play_media = MagicMock()

    mp_living_room = platform.domain_entities["media_player.living_room"]
    mp_living_room.play_media = MagicMock()

    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.PLAY_MEDIA,
        {
            TargetKey.ENTITY_ID: "media_player.media_group",
            MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE: "some_type",
            MediaPlayerServiceArgument.MEDIA_CONTENT_ID: "some_id",
            MediaPlayerServiceArgument.ANNOUNCE: "true",
            MediaPlayerServiceArgument.EXTRA: {
                "volume": 20,
            },
        },
    )
    await hass.async_block_till_done()

    assert mp_bedroom.play_media.call_count == 1
    mp_bedroom.play_media.assert_called_with(
        "some_type", "some_id", announce=True, extra={"volume": 20}
    )

    assert mp_living_room.play_media.call_count == 1
    mp_living_room.play_media.assert_called_with(
        "some_type", "some_id", announce=True, extra={"volume": 20}
    )


async def test_state_listener_removed_with_entity(hass: HomeAssistant) -> None:
    """Test the member state listener is removed when the group is removed."""
    await async_setup_component(
        hass,
        MEDIA_DOMAIN,
        {
            MEDIA_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["media_player.player_1", "media_player.player_2"],
            }
        },
    )
    await hass.async_block_till_done()

    entity = hass.data[MEDIA_DOMAIN].get_entity("media_player.media_group")
    await entity.async_remove()

    assert entity.state is None
    hass.states.async_set("media_player.player_1", STATE_ON)
    await hass.async_block_till_done()

    assert entity.state is None


class MockVolumePlayer(MediaPlayerEntity):
    """Media player with volume controls."""

    _attr_should_poll = False
    _attr_state = MediaPlayerState.ON

    def __init__(
        self,
        name: str,
        volume_level: float | None,
        supported_features: MediaPlayerEntityFeature,
    ) -> None:
        """Initialize the player."""
        self._attr_name = name
        self._attr_volume_level = volume_level
        self._attr_supported_features = supported_features

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()


class MockStepPlayer(MockVolumePlayer):
    """Media player that only steps its volume, in its own increments."""

    async def async_volume_up(self) -> None:
        """Step the volume up."""
        self._attr_volume_level = round(self.volume_level + 0.05, 2)
        self.async_write_ha_state()

    async def async_volume_down(self) -> None:
        """Step the volume down."""
        self._attr_volume_level = round(self.volume_level - 0.05, 2)
        self.async_write_ha_state()


async def _setup_volume_group(hass: HomeAssistant) -> list[MockVolumePlayer]:
    """Set up a group of players with different volume features."""
    players = [
        MockVolumePlayer(
            "Bedroom",
            0.2,
            MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_MUTE,
        ),
        MockVolumePlayer("Kitchen", 0.5, MediaPlayerEntityFeature.VOLUME_SET),
        MockStepPlayer("Living room", 0.8, MediaPlayerEntityFeature.VOLUME_STEP),
        MockVolumePlayer("Mute only", None, MediaPlayerEntityFeature.VOLUME_MUTE),
    ]
    setup_test_component_platform(hass, MEDIA_DOMAIN, players)
    await async_setup_component(
        hass,
        MEDIA_DOMAIN,
        {
            MEDIA_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "media_player.bedroom",
                        "media_player.kitchen",
                        "media_player.living_room",
                        "media_player.mute_only",
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    return players


def _player_attributes(
    hass: HomeAssistant, players: list[MockVolumePlayer], attribute: str
) -> list[Any]:
    """Return an attribute of each player."""
    return [
        hass.states.get(player.entity_id).attributes.get(attribute)
        for player in players
    ]


@pytest.mark.parametrize(
    ("member_features", "expected"),
    [
        pytest.param(
            [MediaPlayerEntityFeature.VOLUME_MUTE],
            MediaPlayerEntityFeature.VOLUME_MUTE,
            id="mute_only",
        ),
        pytest.param(
            [MediaPlayerEntityFeature.VOLUME_STEP],
            MediaPlayerEntityFeature.VOLUME_STEP,
            id="step_only",
        ),
        pytest.param(
            [MediaPlayerEntityFeature.VOLUME_SET],
            MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_STEP,
            id="set_only",
        ),
        pytest.param(
            [MediaPlayerEntityFeature.VOLUME_MUTE, MediaPlayerEntityFeature.VOLUME_SET],
            MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP,
            id="mute_and_set",
        ),
    ],
)
async def test_volume_features_follow_members(
    hass: HomeAssistant,
    member_features: list[MediaPlayerEntityFeature],
    expected: MediaPlayerEntityFeature,
) -> None:
    """Test the group only supports the volume features of its members."""
    await async_setup_component(
        hass,
        MEDIA_DOMAIN,
        {
            MEDIA_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["media_player.player_1", "media_player.player_2"],
            }
        },
    )
    await hass.async_block_till_done()

    for index, features in enumerate(member_features, start=1):
        hass.states.async_set(
            f"media_player.player_{index}",
            STATE_ON,
            {ATTR_SUPPORTED_FEATURES: features},
        )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.media_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == expected


async def test_volume_level_is_average_of_settable_members(
    hass: HomeAssistant,
) -> None:
    """Test the group volume is the average of the members it can set."""
    players = await _setup_volume_group(hass)

    group = hass.states.get("media_player.media_group")
    assert group.attributes[ATTR_MEDIA_VOLUME_LEVEL] == pytest.approx(0.35)

    await players[0].async_set_volume_level(0.6)
    await hass.async_block_till_done()

    group = hass.states.get("media_player.media_group")
    assert group.attributes[ATTR_MEDIA_VOLUME_LEVEL] == pytest.approx(0.55)

    await hass.services.async_call(
        MEDIA_DOMAIN,
        MediaPlayerService.VOLUME_SET,
        {
            TargetKey.ENTITY_ID: "media_player.media_group",
            MediaPlayerServiceArgument.VOLUME_LEVEL: 0.3,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    group = hass.states.get("media_player.media_group")
    assert group.attributes[ATTR_MEDIA_VOLUME_LEVEL] == pytest.approx(0.3)


@pytest.mark.parametrize(
    ("service", "data", "attribute", "expected"),
    [
        pytest.param(
            MediaPlayerService.VOLUME_UP,
            {},
            ATTR_MEDIA_VOLUME_LEVEL,
            [0.3, 0.6, 0.85, None],
            id="volume_up",
        ),
        pytest.param(
            MediaPlayerService.VOLUME_DOWN,
            {},
            ATTR_MEDIA_VOLUME_LEVEL,
            [0.1, 0.4, 0.75, None],
            id="volume_down",
        ),
        pytest.param(
            MediaPlayerService.VOLUME_SET,
            {MediaPlayerServiceArgument.VOLUME_LEVEL: 0.3},
            ATTR_MEDIA_VOLUME_LEVEL,
            [0.3, 0.3, 0.8, None],
            id="volume_set",
        ),
        pytest.param(
            MediaPlayerService.VOLUME_MUTE,
            {MediaPlayerServiceArgument.IS_VOLUME_MUTED: True},
            ATTR_MEDIA_VOLUME_MUTED,
            [True, None, None, True],
            id="volume_mute",
        ),
    ],
)
async def test_volume_services_target_supporting_members(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    service: str,
    data: dict[str, Any],
    attribute: str,
    expected: list[Any],
) -> None:
    """Test volume services reach each member that supports them."""
    players = await _setup_volume_group(hass)

    await hass.services.async_call(
        MEDIA_DOMAIN,
        service,
        {TargetKey.ENTITY_ID: "media_player.media_group", **data},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _player_attributes(hass, players, attribute) == pytest.approx(expected)
    assert not [record for record in caplog.records if record.levelno >= ERROR]
