"""Test the jellyfin media source."""
import pytest

from homeassistant.components import media_source
from homeassistant.components.jellyfin.const import (
    DOMAIN,
    MAX_IMAGE_WIDTH,
    MAX_STREAMING_BITRATE,
    MEDIA_TYPE_NONE,
)
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_TRACK,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source import const
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_mock_jellyfin_config_entry
from .const import (
    MOCK_ALBUM_FOLDER,
    MOCK_ALBUM_FOLDER_ID,
    MOCK_ALBUM_ID,
    MOCK_ALBUM_NAME,
    MOCK_ARTIST_ID,
    MOCK_ARTIST_NAME,
    MOCK_AUTH_TOKEN,
    MOCK_FOLDER,
    MOCK_FOLDER_ID,
    MOCK_INVALID_SOURCE_TRACK_ID,
    MOCK_MOVIE_ID,
    MOCK_NO_INDEX_ALBUM_ID,
    MOCK_NO_INDEX_ALBUM_NAME,
    MOCK_NO_INDEX_TRACK_ID,
    MOCK_NO_INDEX_TRACK_NAME,
    MOCK_NO_SOURCE_TRACK_ID,
    MOCK_TRACK_ID,
    MOCK_TRACK_NAME,
    MOCK_USER_ID,
    MOCK_VIDEO_FOLDER_ID,
    TEST_URL,
)


async def test_async_browse_media(hass: HomeAssistant) -> None:
    """Test browse media with the default artist -> album -> track hierarchy."""
    await setup_mock_jellyfin_config_entry(hass)

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    media = await media_source.async_browse_media(
        hass,
        f"{const.URI_SCHEME}{DOMAIN}",
    )

    assert media.as_dict() == {
        "media_class": MEDIA_CLASS_DIRECTORY,
        "media_content_id": f"{const.URI_SCHEME}{DOMAIN}",
        "media_content_type": MEDIA_TYPE_NONE,
        "not_shown": 0,
        "thumbnail": None,
        "title": "Jellyfin",
        "can_play": False,
        "can_expand": True,
        "children": [
            {
                "can_expand": True,
                "can_play": False,
                "children_media_class": None,
                "media_class": MEDIA_CLASS_DIRECTORY,
                "media_content_id": f"{const.URI_SCHEME}{DOMAIN}/{MOCK_FOLDER_ID}",
                "media_content_type": "",
                "thumbnail": None,
                "title": MOCK_FOLDER,
            }
        ],
        "children_media_class": MEDIA_CLASS_DIRECTORY,
    }

    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{MOCK_FOLDER_ID}"
    )

    assert media.as_dict() == {
        "media_class": MEDIA_CLASS_DIRECTORY,
        "media_content_id": f"{const.URI_SCHEME}{DOMAIN}/{MOCK_FOLDER_ID}",
        "media_content_type": MEDIA_TYPE_NONE,
        "not_shown": 0,
        "thumbnail": None,
        "title": MOCK_FOLDER,
        "can_play": False,
        "can_expand": True,
        "children": [
            {
                "can_expand": True,
                "can_play": False,
                "children_media_class": None,
                "media_class": MEDIA_CLASS_ARTIST,
                "media_content_id": f"{const.URI_SCHEME}{DOMAIN}/{MOCK_ARTIST_ID}",
                "media_content_type": "",
                "thumbnail": f"{TEST_URL}/Items/{MOCK_ARTIST_ID}/Images/Primary?MaxWidth={MAX_IMAGE_WIDTH}&format=jpg",
                "title": MOCK_ARTIST_NAME,
            },
        ],
        "children_media_class": MEDIA_CLASS_ARTIST,
    }

    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{MOCK_ARTIST_ID}"
    )

    assert media.as_dict() == {
        "media_class": MEDIA_CLASS_ARTIST,
        "media_content_id": f"{const.URI_SCHEME}{DOMAIN}/{MOCK_ARTIST_ID}",
        "media_content_type": MEDIA_TYPE_NONE,
        "not_shown": 0,
        "thumbnail": f"{TEST_URL}/Items/{MOCK_ARTIST_ID}/Images/Primary?MaxWidth={MAX_IMAGE_WIDTH}&format=jpg",
        "title": MOCK_ARTIST_NAME,
        "can_play": False,
        "can_expand": True,
        "children": [
            {
                "can_expand": True,
                "can_play": False,
                "children_media_class": None,
                "media_class": MEDIA_CLASS_ALBUM,
                "media_content_id": f"{const.URI_SCHEME}{DOMAIN}/{MOCK_ALBUM_ID}",
                "media_content_type": "",
                "thumbnail": None,
                "title": MOCK_ALBUM_NAME,
            },
        ],
        "children_media_class": MEDIA_CLASS_ALBUM,
    }

    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{MOCK_ALBUM_ID}"
    )

    assert media.as_dict() == {
        "media_class": MEDIA_CLASS_ALBUM,
        "media_content_id": f"{const.URI_SCHEME}{DOMAIN}/{MOCK_ALBUM_ID}",
        "media_content_type": MEDIA_TYPE_NONE,
        "not_shown": 0,
        "thumbnail": None,
        "title": MOCK_ALBUM_NAME,
        "can_play": False,
        "can_expand": True,
        "children": [
            {
                "can_expand": False,
                "can_play": True,
                "children_media_class": None,
                "media_class": MEDIA_CLASS_TRACK,
                "media_content_id": f"{const.URI_SCHEME}{DOMAIN}/{MOCK_TRACK_ID}",
                "media_content_type": "audio/flac",
                "thumbnail": f"{TEST_URL}/Items/{MOCK_TRACK_ID}/Images/Primary?MaxWidth={MAX_IMAGE_WIDTH}&format=jpg",
                "title": MOCK_TRACK_NAME,
            }
        ],
        "children_media_class": MEDIA_CLASS_TRACK,
    }


async def test_async_browse_album_library(hass: HomeAssistant) -> None:
    """Test browse media hierarchy with no artist level."""
    await setup_mock_jellyfin_config_entry(hass)

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{MOCK_ALBUM_FOLDER_ID}"
    )

    assert media.as_dict() == {
        "media_class": MEDIA_CLASS_DIRECTORY,
        "media_content_id": f"{const.URI_SCHEME}{DOMAIN}/{MOCK_ALBUM_FOLDER_ID}",
        "media_content_type": MEDIA_TYPE_NONE,
        "not_shown": 0,
        "thumbnail": None,
        "title": MOCK_ALBUM_FOLDER,
        "can_play": False,
        "can_expand": True,
        "children": [
            {
                "can_expand": True,
                "can_play": False,
                "children_media_class": None,
                "media_class": MEDIA_CLASS_ALBUM,
                "media_content_id": f"{const.URI_SCHEME}{DOMAIN}/{MOCK_ALBUM_ID}",
                "media_content_type": "",
                "thumbnail": None,
                "title": MOCK_ALBUM_NAME,
            },
        ],
        "children_media_class": MEDIA_CLASS_ALBUM,
    }


async def test_async_browse_album_no_index_library(hass: HomeAssistant) -> None:
    """Test browsing album with tracks with no indices."""
    await setup_mock_jellyfin_config_entry(hass)

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{MOCK_NO_INDEX_ALBUM_ID}"
    )

    assert media.as_dict() == {
        "media_class": MEDIA_CLASS_ALBUM,
        "media_content_id": f"{const.URI_SCHEME}{DOMAIN}/{MOCK_NO_INDEX_ALBUM_ID}",
        "media_content_type": MEDIA_TYPE_NONE,
        "not_shown": 0,
        "thumbnail": None,
        "title": MOCK_NO_INDEX_ALBUM_NAME,
        "can_play": False,
        "can_expand": True,
        "children": [
            {
                "can_expand": False,
                "can_play": True,
                "children_media_class": None,
                "media_class": MEDIA_CLASS_TRACK,
                "media_content_id": f"{const.URI_SCHEME}{DOMAIN}/{MOCK_NO_INDEX_TRACK_ID}",
                "media_content_type": "audio/flac",
                "thumbnail": f"{TEST_URL}/Items/{MOCK_NO_INDEX_TRACK_ID}/Images/Primary?MaxWidth={MAX_IMAGE_WIDTH}&format=jpg",
                "title": MOCK_NO_INDEX_TRACK_NAME,
            }
        ],
        "children_media_class": MEDIA_CLASS_TRACK,
    }


async def test_async_browse_video_library(hass: HomeAssistant) -> None:
    """Test browse media with an invalid collection type."""
    await setup_mock_jellyfin_config_entry(hass)

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(BrowseError):
        await media_source.async_browse_media(
            hass, f"{const.URI_SCHEME}{DOMAIN}/{MOCK_VIDEO_FOLDER_ID}"
        )


async def test_async_browse_movie(hass: HomeAssistant) -> None:
    """Test browse media with an invalid item type."""
    await setup_mock_jellyfin_config_entry(hass)

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(BrowseError):
        await media_source.async_browse_media(
            hass, f"{const.URI_SCHEME}{DOMAIN}/{MOCK_MOVIE_ID}"
        )


async def test_async_resolve_media(hass: HomeAssistant) -> None:
    """Test resolving the URL for a valid item."""
    await setup_mock_jellyfin_config_entry(hass)

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    play_media = await media_source.async_resolve_media(
        hass,
        f"{const.URI_SCHEME}{DOMAIN}/{MOCK_TRACK_ID}",
    )

    assert (
        play_media.url
        == f"{TEST_URL}/Audio/{MOCK_TRACK_ID}/universal?UserId={MOCK_USER_ID}&DeviceId=Home+Assistant&api_key={MOCK_AUTH_TOKEN}&MaxStreamingBitrate={MAX_STREAMING_BITRATE}"
    )


async def test_async_resolve_movie(hass: HomeAssistant) -> None:
    """Test resolving the URL for an unsupported item."""
    await setup_mock_jellyfin_config_entry(hass)

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(BrowseError):
        await media_source.async_resolve_media(
            hass,
            f"{const.URI_SCHEME}{DOMAIN}/{MOCK_MOVIE_ID}",
        )


async def test_async_resolve_no_source_track(hass: HomeAssistant) -> None:
    """Test resolving the URL for a track without a source."""
    await setup_mock_jellyfin_config_entry(hass)

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(BrowseError):
        await media_source.async_resolve_media(
            hass,
            f"{const.URI_SCHEME}{DOMAIN}/{MOCK_NO_SOURCE_TRACK_ID}",
        )


async def test_async_resolve_invalid_source_track(hass: HomeAssistant) -> None:
    """Test resolving the URL for a track with an invalid source."""
    await setup_mock_jellyfin_config_entry(hass)

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(BrowseError):
        await media_source.async_resolve_media(
            hass,
            f"{const.URI_SCHEME}{DOMAIN}/{MOCK_INVALID_SOURCE_TRACK_ID}",
        )
