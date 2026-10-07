"""Test media source helpers."""

import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseError,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.components.media_source import const, models
from homeassistant.components.media_source.const import DATA_MEDIA_SOURCE_PLATFORMS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component


async def test_async_browse_media(hass: HomeAssistant) -> None:
    """Test browse media."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()

    # Test non-media ignored (/media has test.mp3 and not_media.txt)
    media = await media_source.async_browse_media(hass, "")
    assert isinstance(media, media_source.models.BrowseMediaSource)
    assert media.title == "media"
    assert len(media.children) == 3

    # Test content filter
    media = await media_source.async_browse_media(
        hass,
        "",
        content_filter=lambda item: item.media_content_type.startswith("video/"),
    )
    assert isinstance(media, media_source.models.BrowseMediaSource)
    assert media.title == "media"
    assert len(media.children) == 1, media.children
    media.children[0].title = "Epic Sax Guy 10 Hours"
    assert media.not_shown == 2

    # Test content filter adds to original not_shown
    orig_browse = models.MediaSourceItem.async_browse

    async def not_shown_browse(self):
        """Patch browsed item to set not_shown base value."""
        item = await orig_browse(self)
        item.not_shown = 10
        return item

    with patch(
        "homeassistant.components.media_source.models.MediaSourceItem.async_browse",
        not_shown_browse,
    ):
        media = await media_source.async_browse_media(
            hass,
            "",
            content_filter=lambda item: item.media_content_type.startswith("video/"),
        )
    assert isinstance(media, media_source.models.BrowseMediaSource)
    assert media.title == "media"
    assert len(media.children) == 1, media.children
    media.children[0].title = "Epic Sax Guy 10 Hours"
    assert media.not_shown == 12

    # Test invalid media content
    with pytest.raises(BrowseError):
        await media_source.async_browse_media(hass, "invalid")

    # Test base URI returns all domains
    media = await media_source.async_browse_media(hass, const.URI_SCHEME)
    assert isinstance(media, media_source.models.RootBrowseMediaSource)
    assert len(media.children) == 1
    assert media.children[0].title == "My media"


async def test_async_resolve_media(hass: HomeAssistant) -> None:
    """Test browse media."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()

    media = await media_source.async_resolve_media(
        hass,
        media_source.generate_media_source_id(media_source.DOMAIN, "local/test.mp3"),
        None,
    )
    assert isinstance(media, media_source.models.PlayMedia)
    assert media.url == "/media/local/test.mp3"
    assert media.mime_type == "audio/mpeg"


async def test_async_resolve_media_no_entity(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test browse media."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(RuntimeError):
        await media_source.async_resolve_media(
            hass,
            media_source.generate_media_source_id(
                media_source.DOMAIN, "local/test.mp3"
            ),
        )


async def test_async_unresolve_media(hass: HomeAssistant) -> None:
    """Test browse media."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()

    # Test no media content
    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(hass, "", None)

    # Test invalid media content
    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(hass, "invalid", None)

    # Test invalid media source
    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(
            hass, "media-source://media_source2", None
        )


async def test_browse_resolve_without_setup(hass: HomeAssistant) -> None:
    """Test browse and resolve work without being setup."""
    with pytest.raises(BrowseError):
        await media_source.async_browse_media(hass, None)

    with pytest.raises(BrowseError):
        await media_source.async_search_media(
            hass, None, SearchMediaQuery(search_query="test")
        )

    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(hass, None, None)


async def test_async_search_media(hass: HomeAssistant) -> None:
    """Test search media helper."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()

    # Search the default media directory by file name
    result = await media_source.async_search_media(
        hass, "", SearchMediaQuery(search_query="test")
    )
    assert isinstance(result, SearchMedia)
    assert [item.title for item in result.result] == ["test.mp3"]

    # A query without matches returns an empty result
    result = await media_source.async_search_media(
        hass, "", SearchMediaQuery(search_query="no-such-file")
    )
    assert result.result == []

    # Invalid media content raises a BrowseError
    with pytest.raises(BrowseError):
        await media_source.async_search_media(
            hass, "invalid", SearchMediaQuery(search_query="test")
        )


async def test_async_search_media_not_supported(hass: HomeAssistant) -> None:
    """Test searching a source without search support raises a BrowseError."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()
    hass.data[DATA_MEDIA_SOURCE_PLATFORMS].async_get_platform = AsyncMock(
        return_value=models.MediaSource("plain")
    )

    with pytest.raises(BrowseError):
        await media_source.async_search_media(
            hass,
            f"{const.URI_SCHEME}plain",
            SearchMediaQuery(search_query="test"),
        )


async def test_async_search_media_root_not_supported(hass: HomeAssistant) -> None:
    """Test searching the aggregate root of multiple sources is not supported."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()
    hass.data[DATA_MEDIA_SOURCE_PLATFORMS].async_get_platforms = AsyncMock(
        return_value={"source_a": models.MediaSource("source_a")}
    )

    with pytest.raises(BrowseError):
        await media_source.async_search_media(
            hass, "", SearchMediaQuery(search_query="test")
        )


async def test_async_get_media_image(hass: HomeAssistant) -> None:
    """Test getting an image from a source that provides images."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()
    source = models.MediaSource("plain")
    source.async_get_media_image = AsyncMock(
        return_value=media_source.MediaImage(b"image", "image/png")
    )
    hass.data[DATA_MEDIA_SOURCE_PLATFORMS].async_get_platform = AsyncMock(
        return_value=source
    )

    assert await media_source.async_get_media_image(
        hass, f"{const.URI_SCHEME}plain/item"
    ) == media_source.MediaImage(b"image", "image/png")


@pytest.mark.parametrize(
    "media_content_id",
    [
        pytest.param("", id="root"),
        pytest.param("invalid", id="invalid"),
        pytest.param(f"{const.URI_SCHEME}unknown", id="unknown_source"),
        pytest.param(
            f"{const.URI_SCHEME}{media_source.DOMAIN}/local/test.mp3",
            id="no_image_support",
        ),
    ],
)
async def test_async_get_media_image_none(
    hass: HomeAssistant, media_content_id: str
) -> None:
    """Test no image is returned if the source can not provide one."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()

    assert await media_source.async_get_media_image(hass, media_content_id) is None


async def test_async_get_media_image_without_setup(hass: HomeAssistant) -> None:
    """Test no image is returned if media source is not set up."""
    assert (
        await media_source.async_get_media_image(
            hass, f"{const.URI_SCHEME}camera/camera.demo_camera"
        )
        is None
    )


async def test_async_get_media_image_error(hass: HomeAssistant) -> None:
    """Test errors of the source are raised."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()
    source = models.MediaSource("plain")
    source.async_get_media_image = AsyncMock(
        side_effect=HomeAssistantError("Unable to get image")
    )
    hass.data[DATA_MEDIA_SOURCE_PLATFORMS].async_get_platform = AsyncMock(
        return_value=source
    )

    with pytest.raises(HomeAssistantError, match="Unable to get image"):
        await media_source.async_get_media_image(hass, f"{const.URI_SCHEME}plain/item")


async def test_async_get_media_image_cancelled(hass: HomeAssistant) -> None:
    """Test cancellation suppressed by the source is restored."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()
    started = asyncio.Event()

    async def _get_media_image(
        item: media_source.MediaSourceItem,
    ) -> media_source.MediaImage:
        # Mimic camera and image suppressing the cancellation
        with suppress(asyncio.CancelledError):
            started.set()
            await asyncio.Event().wait()
        raise HomeAssistantError("Unable to get image")

    source = models.MediaSource("plain")
    source.async_get_media_image = _get_media_image
    hass.data[DATA_MEDIA_SOURCE_PLATFORMS].async_get_platform = AsyncMock(
        return_value=source
    )

    task = hass.async_create_task(
        media_source.async_get_media_image(hass, f"{const.URI_SCHEME}plain/item")
    )
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
