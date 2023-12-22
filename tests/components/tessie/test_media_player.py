"""Test the Tessie media player platform."""
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_PLAYLIST,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_TITLE,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant

from .common import TEST_STATE_OF_ALL_VEHICLES, setup_platform

MEDIA_INFO = TEST_STATE_OF_ALL_VEHICLES["results"][0]["last_state"]["vehicle_state"][
    "media_info"
]


async def test_sensors(hass: HomeAssistant) -> None:
    """Tests that the media player entity is correct."""

    assert len(hass.states.async_all("media_player")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("media_player")) == 1

    state = hass.states.get("media_player.test")
    assert state.state == MediaPlayerState.PLAYING
    assert state.attributes["volume_level"] == 2.3333 / 10.333333
    assert state.attributes[ATTR_MEDIA_TITLE] == MEDIA_INFO["now_playing_title"]
    assert state.attributes[ATTR_MEDIA_ARTIST] == MEDIA_INFO["now_playing_artist"]
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == MEDIA_INFO["now_playing_album"]
    assert state.attributes[ATTR_INPUT_SOURCE] == MEDIA_INFO["now_playing_source"]
    assert state.attributes[ATTR_MEDIA_PLAYLIST] == MEDIA_INFO["now_playing_station"]
    assert (
        state.attributes[ATTR_MEDIA_DURATION]
        == MEDIA_INFO["now_playing_duration"] / 1000
    )
    assert (
        state.attributes[ATTR_MEDIA_POSITION]
        == MEDIA_INFO["now_playing_elapsed"] / 1000
    )
