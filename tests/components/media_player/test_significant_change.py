"""Test the Media Player significant change platform."""
import pytest

from homeassistant.components.media_player import (
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_ENTITY_PICTURE_LOCAL,
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_EPISODE,
    ATTR_MEDIA_PLAYLIST,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEASON,
    ATTR_MEDIA_SERIES_TITLE,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
)
from homeassistant.components.media_player.significant_change import (
    async_check_significant_change,
)


async def test_significant_state_change() -> None:
    """Detect Media Player significant state changes."""
    attrs = {}
    assert not async_check_significant_change(None, "on", attrs, "on", attrs)
    assert async_check_significant_change(None, "on", attrs, "off", attrs)


@pytest.mark.parametrize(
    ("old_attrs", "new_attrs", "expected_result"),
    [
        ({ATTR_APP_ID: "old_value"}, {ATTR_APP_ID: "old_value"}, False),
        ({ATTR_APP_ID: "old_value"}, {ATTR_APP_ID: "new_value"}, True),
        ({ATTR_APP_NAME: "old_value"}, {ATTR_APP_NAME: "new_value"}, True),
        (
            {ATTR_ENTITY_PICTURE_LOCAL: "old_value"},
            {ATTR_ENTITY_PICTURE_LOCAL: "new_value"},
            True,
        ),
        (
            {ATTR_GROUP_MEMBERS: ["old1", "old2"]},
            {ATTR_GROUP_MEMBERS: ["old1", "new"]},
            False,
        ),
        ({ATTR_INPUT_SOURCE: "old_value"}, {ATTR_INPUT_SOURCE: "new_value"}, True),
        (
            {ATTR_MEDIA_ALBUM_ARTIST: "old_value"},
            {ATTR_MEDIA_ALBUM_ARTIST: "new_value"},
            True,
        ),
        (
            {ATTR_MEDIA_ALBUM_NAME: "old_value"},
            {ATTR_MEDIA_ALBUM_NAME: "new_value"},
            True,
        ),
        ({ATTR_MEDIA_ARTIST: "old_value"}, {ATTR_MEDIA_ARTIST: "new_value"}, True),
        ({ATTR_MEDIA_CHANNEL: "old_value"}, {ATTR_MEDIA_CHANNEL: "new_value"}, True),
        (
            {ATTR_MEDIA_CONTENT_ID: "old_value"},
            {ATTR_MEDIA_CONTENT_ID: "new_value"},
            True,
        ),
        (
            {ATTR_MEDIA_CONTENT_TYPE: "old_value"},
            {ATTR_MEDIA_CONTENT_TYPE: "new_value"},
            True,
        ),
        ({ATTR_MEDIA_DURATION: "old_value"}, {ATTR_MEDIA_DURATION: "new_value"}, True),
        ({ATTR_MEDIA_EPISODE: "old_value"}, {ATTR_MEDIA_EPISODE: "new_value"}, True),
        ({ATTR_MEDIA_PLAYLIST: "old_value"}, {ATTR_MEDIA_PLAYLIST: "new_value"}, True),
        ({ATTR_MEDIA_REPEAT: "old_value"}, {ATTR_MEDIA_REPEAT: "new_value"}, True),
        ({ATTR_MEDIA_SEASON: "old_value"}, {ATTR_MEDIA_SEASON: "new_value"}, True),
        (
            {ATTR_MEDIA_SERIES_TITLE: "old_value"},
            {ATTR_MEDIA_SERIES_TITLE: "new_value"},
            True,
        ),
        ({ATTR_MEDIA_SHUFFLE: "old_value"}, {ATTR_MEDIA_SHUFFLE: "new_value"}, True),
        ({ATTR_MEDIA_TITLE: "old_value"}, {ATTR_MEDIA_TITLE: "new_value"}, True),
        ({ATTR_MEDIA_TRACK: "old_value"}, {ATTR_MEDIA_TRACK: "new_value"}, True),
        (
            {ATTR_MEDIA_VOLUME_MUTED: "old_value"},
            {ATTR_MEDIA_VOLUME_MUTED: "new_value"},
            True,
        ),
        ({ATTR_SOUND_MODE: "old_value"}, {ATTR_SOUND_MODE: "new_value"}, True),
        # multiple attributes
        (
            {ATTR_SOUND_MODE: "old_value", ATTR_MEDIA_VOLUME_MUTED: "old_value"},
            {ATTR_SOUND_MODE: "new_value", ATTR_MEDIA_VOLUME_MUTED: "old_value"},
            True,
        ),
        # float attributes
        ({ATTR_MEDIA_VOLUME_LEVEL: 0.1}, {ATTR_MEDIA_VOLUME_LEVEL: 0.2}, True),
        ({ATTR_MEDIA_VOLUME_LEVEL: 0.1}, {ATTR_MEDIA_VOLUME_LEVEL: 0.19}, False),
        ({ATTR_MEDIA_VOLUME_LEVEL: "invalid"}, {ATTR_MEDIA_VOLUME_LEVEL: 1}, True),
        ({ATTR_MEDIA_VOLUME_LEVEL: 1}, {ATTR_MEDIA_VOLUME_LEVEL: "invalid"}, False),
        # insignificant attributes
        ({ATTR_MEDIA_POSITION: "old_value"}, {ATTR_MEDIA_POSITION: "new_value"}, False),
        (
            {ATTR_MEDIA_POSITION_UPDATED_AT: "old_value"},
            {ATTR_MEDIA_POSITION_UPDATED_AT: "new_value"},
            False,
        ),
        ({"unknown_attr": "old_value"}, {"unknown_attr": "old_value"}, False),
        ({"unknown_attr": "old_value"}, {"unknown_attr": "new_value"}, False),
    ],
)
async def test_significant_atributes_change(
    old_attrs: dict, new_attrs: dict, expected_result: bool
) -> None:
    """Detect Media Player significant attribute changes."""
    assert (
        async_check_significant_change(None, "state", old_attrs, "state", new_attrs)
        == expected_result
    )
