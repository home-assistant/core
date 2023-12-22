"""Test the Tessie media player platform."""

from datetime import timedelta

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_PLAYLIST,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    MediaPlayerState,
)
from homeassistant.components.tessie.coordinator import TESSIE_SYNC_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .common import (
    TEST_STATE_OF_ALL_VEHICLES,
    TEST_VEHICLE_STATE_ONLINE,
    setup_platform,
)

from tests.common import async_fire_time_changed

WAIT = timedelta(seconds=TESSIE_SYNC_INTERVAL)

MEDIA_INFO_1 = TEST_STATE_OF_ALL_VEHICLES["results"][0]["last_state"]["vehicle_state"][
    "media_info"
]
MEDIA_INFO_2 = TEST_VEHICLE_STATE_ONLINE["vehicle_state"]["media_info"]


async def test_sensors(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the media player entity is correct."""

    assert len(hass.states.async_all("media_player")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("media_player")) == 1

    state = hass.states.get("media_player.test")
    assert state.state == MediaPlayerState.IDLE
    assert (
        state.attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == MEDIA_INFO_1["audio_volume"] / MEDIA_INFO_1["audio_volume_max"]
    )
    assert ATTR_MEDIA_TITLE not in state.attributes
    assert ATTR_MEDIA_ARTIST not in state.attributes
    assert ATTR_MEDIA_ALBUM_NAME not in state.attributes
    assert ATTR_INPUT_SOURCE not in state.attributes
    assert ATTR_MEDIA_PLAYLIST not in state.attributes
    assert ATTR_MEDIA_DURATION not in state.attributes
    assert ATTR_MEDIA_POSITION not in state.attributes

    # Trigger coordinator refresh since it has a different fixture.

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.test")
    assert state.state == MediaPlayerState.PLAYING
    assert (
        state.attributes[ATTR_MEDIA_VOLUME_LEVEL]
        == MEDIA_INFO_2["audio_volume"] / MEDIA_INFO_2["audio_volume_max"]
    )
    assert state.attributes[ATTR_MEDIA_TITLE] == MEDIA_INFO_2["now_playing_title"]
    assert state.attributes[ATTR_MEDIA_ARTIST] == MEDIA_INFO_2["now_playing_artist"]
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == MEDIA_INFO_2["now_playing_album"]
    assert state.attributes[ATTR_INPUT_SOURCE] == MEDIA_INFO_2["now_playing_source"]
    assert state.attributes[ATTR_MEDIA_PLAYLIST] == MEDIA_INFO_2["now_playing_station"]
    assert (
        state.attributes[ATTR_MEDIA_DURATION]
        == MEDIA_INFO_2["now_playing_duration"] / 1000
    )
    assert (
        state.attributes[ATTR_MEDIA_POSITION]
        == MEDIA_INFO_2["now_playing_elapsed"] / 1000
    )
