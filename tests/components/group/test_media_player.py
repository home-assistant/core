"""The tests for the Media group platform."""
from unittest.mock import Mock, patch

import async_timeout
import pytest

from homeassistant.components.group import DOMAIN
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_SEEK,
    SERVICE_PLAY_MEDIA,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_SET,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


@pytest.fixture(name="mock_media_seek")
def media_player_media_seek_fixture():
    """Mock demo YouTube player media seek."""
    with patch(
        "homeassistant.components.demo.media_player.DemoYoutubePlayer.media_seek",
        autospec=True,
    ) as seek:
        yield seek


async def test_default_state(hass: HomeAssistant) -> None:
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

    entity_registry = er.async_get(hass)
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
    Otherwise, the group state is on if at least one group member is not off, unavailable or unknown.
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
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_OFF
    assert hass.states.get("media_player.kitchen").state == STATE_OFF
    assert hass.states.get("media_player.living_room").state == STATE_OFF

    await hass.services.async_call(
        MEDIA_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_PLAYING
    assert hass.states.get("media_player.kitchen").state == STATE_PLAYING
    assert hass.states.get("media_player.living_room").state == STATE_PLAYING

    await hass.services.async_call(
        MEDIA_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_PAUSED
    assert hass.states.get("media_player.kitchen").state == STATE_PAUSED
    assert hass.states.get("media_player.living_room").state == STATE_PAUSED

    await hass.services.async_call(
        MEDIA_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: "media_player.media_group"},
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
        SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_TRACK] == 2

    await hass.services.async_call(
        MEDIA_DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.kitchen").attributes[ATTR_MEDIA_TRACK] == 1

    await hass.services.async_call(
        MEDIA_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.media_group",
            ATTR_MEDIA_CONTENT_TYPE: "some_type",
            ATTR_MEDIA_CONTENT_ID: "some_id",
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
        SERVICE_MEDIA_SEEK,
        {
            ATTR_ENTITY_ID: "media_player.media_group",
            ATTR_MEDIA_SEEK_POSITION: 100,
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
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: "media_player.media_group",
            ATTR_MEDIA_VOLUME_LEVEL: 0.5,
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
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: "media_player.media_group"},
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
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: "media_player.media_group"},
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
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: "media_player.media_group", ATTR_MEDIA_VOLUME_MUTED: True},
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
        SERVICE_SHUFFLE_SET,
        {ATTR_ENTITY_ID: "media_player.media_group", ATTR_MEDIA_SHUFFLE: True},
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
        SERVICE_CLEAR_PLAYLIST,
        {ATTR_ENTITY_ID: "media_player.media_group"},
        blocking=True,
    )
    await hass.async_block_till_done()
    # SERVICE_CLEAR_PLAYLIST is not supported by bedroom and living_room players
    assert hass.states.get("media_player.kitchen").state == STATE_OFF

    await hass.services.async_call(
        MEDIA_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: "media_player.kitchen"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_PLAYING
    assert hass.states.get("media_player.kitchen").state == STATE_PLAYING
    assert hass.states.get("media_player.living_room").state == STATE_PLAYING
    await hass.services.async_call(
        MEDIA_DOMAIN,
        SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: "media_player.media_group"},
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
    async with async_timeout.timeout(0.5):
        await hass.services.async_call(
            MEDIA_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "media_player.group_1"},
            blocking=True,
        )

    await hass.async_block_till_done()
    assert hass.states.get("media_player.bedroom").state == STATE_OFF
    assert hass.states.get("media_player.kitchen").state == STATE_OFF
    assert hass.states.get("media_player.group_1").state == STATE_OFF
    assert hass.states.get("media_player.nested_group").state == STATE_OFF
