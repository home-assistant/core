"""Test the Media Player significant change platform."""

import pytest

from homeassistant.components.media_player import MediaPlayerEntityStateAttribute
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
        (
            {MediaPlayerEntityStateAttribute.APP_ID: "old_value"},
            {MediaPlayerEntityStateAttribute.APP_ID: "old_value"},
            False,
        ),
        (
            {MediaPlayerEntityStateAttribute.APP_ID: "old_value"},
            {MediaPlayerEntityStateAttribute.APP_ID: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.APP_NAME: "old_value"},
            {MediaPlayerEntityStateAttribute.APP_NAME: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.ENTITY_PICTURE_LOCAL: "old_value"},
            {MediaPlayerEntityStateAttribute.ENTITY_PICTURE_LOCAL: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.GROUP_MEMBERS: ["old1", "old2"]},
            {MediaPlayerEntityStateAttribute.GROUP_MEMBERS: ["old1", "new"]},
            False,
        ),
        (
            {MediaPlayerEntityStateAttribute.INPUT_SOURCE: "old_value"},
            {MediaPlayerEntityStateAttribute.INPUT_SOURCE: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_ALBUM_ARTIST: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_ALBUM_ARTIST: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_ALBUM_NAME: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_ALBUM_NAME: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_ARTIST: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_ARTIST: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_CHANNEL: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_CHANNEL: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_CONTENT_ID: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_CONTENT_ID: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_CONTENT_TYPE: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_CONTENT_TYPE: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_DURATION: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_DURATION: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_EPISODE: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_EPISODE: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_PLAYLIST: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_PLAYLIST: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_REPEAT: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_REPEAT: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_SEASON: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_SEASON: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_SERIES_TITLE: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_SERIES_TITLE: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_SHUFFLE: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_SHUFFLE: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_TITLE: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_TITLE: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_TRACK: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_TRACK: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_VOLUME_MUTED: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_VOLUME_MUTED: "new_value"},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.SOUND_MODE: "old_value"},
            {MediaPlayerEntityStateAttribute.SOUND_MODE: "new_value"},
            True,
        ),
        # multiple attributes
        (
            {
                MediaPlayerEntityStateAttribute.SOUND_MODE: "old_value",
                MediaPlayerEntityStateAttribute.MEDIA_VOLUME_MUTED: "old_value",
            },
            {
                MediaPlayerEntityStateAttribute.SOUND_MODE: "new_value",
                MediaPlayerEntityStateAttribute.MEDIA_VOLUME_MUTED: "old_value",
            },
            True,
        ),
        # float attributes
        (
            {MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL: 0.1},
            {MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL: 0.2},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL: 0.1},
            {MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL: 0.19},
            False,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL: "invalid"},
            {MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL: 1},
            True,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL: 1},
            {MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL: "invalid"},
            False,
        ),
        # insignificant attributes
        (
            {MediaPlayerEntityStateAttribute.MEDIA_POSITION: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_POSITION: "new_value"},
            False,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_POSITION_UPDATED_AT: "old_value"},
            {MediaPlayerEntityStateAttribute.MEDIA_POSITION_UPDATED_AT: "new_value"},
            False,
        ),
        # unhashable attribute values
        (
            {MediaPlayerEntityStateAttribute.MEDIA_CONTENT_ID: {"tvdb": "1"}},
            {MediaPlayerEntityStateAttribute.MEDIA_CONTENT_ID: {"tvdb": "1"}},
            False,
        ),
        (
            {MediaPlayerEntityStateAttribute.MEDIA_CONTENT_ID: {"tvdb": "1"}},
            {MediaPlayerEntityStateAttribute.MEDIA_CONTENT_ID: {"tvdb": "2"}},
            True,
        ),
        ({}, {MediaPlayerEntityStateAttribute.MEDIA_CONTENT_ID: {"tvdb": "1"}}, True),
        # an attribute that appears or disappears is a change, even as None
        ({}, {MediaPlayerEntityStateAttribute.MEDIA_TITLE: None}, True),
        ({MediaPlayerEntityStateAttribute.MEDIA_TITLE: None}, {}, True),
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
