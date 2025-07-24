"""Tests for Immich media source."""

from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from aiohttp import web
from aioimmich.exceptions import ImmichError
import pytest

from homeassistant.components.immich.const import DOMAIN
from homeassistant.components.immich.media_source import (
    ImmichMediaSource,
    ImmichMediaView,
    async_get_media_source,
)
from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_source import (
    BrowseError,
    BrowseMedia,
    MediaSourceItem,
    Unresolvable,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.aiohttp import MockRequest, MockStreamReaderChunked

from . import setup_integration
from .const import MOCK_ALBUM_WITHOUT_ASSETS

from tests.common import MockConfigEntry


async def test_get_media_source(hass: HomeAssistant) -> None:
    """Test the async_get_media_source."""
    assert await async_setup_component(hass, "media_source", {})

    source = await async_get_media_source(hass)
    assert isinstance(source, ImmichMediaSource)
    assert source.domain == DOMAIN


@pytest.mark.parametrize(
    ("identifier", "exception_msg"),
    [
        ("unique_id", "Could not resolve identifier that has no mime-type"),
        (
            "unique_id|albums|album_id",
            "Could not resolve identifier that has no mime-type",
        ),
        (
            "unique_id|albums|album_id|asset_id|filename",
            "Could not parse identifier",
        ),
    ],
)
async def test_resolve_media_bad_identifier(
    hass: HomeAssistant, identifier: str, exception_msg: str
) -> None:
    """Test resolve_media with bad identifiers."""
    assert await async_setup_component(hass, "media_source", {})

    source = await async_get_media_source(hass)
    item = MediaSourceItem(hass, DOMAIN, identifier, None)
    with pytest.raises(Unresolvable, match=exception_msg):
        await source.async_resolve_media(item)


@pytest.mark.parametrize(
    ("identifier", "url", "mime_type"),
    [
        (
            "unique_id|albums|album_id|asset_id|filename.jpg|image/jpeg",
            "/immich/unique_id/asset_id/fullsize/image/jpeg",
            "image/jpeg",
        ),
        (
            "unique_id|albums|album_id|asset_id|filename.png|image/png",
            "/immich/unique_id/asset_id/fullsize/image/png",
            "image/png",
        ),
        (
            "unique_id|albums|album_id|asset_id|filename.mp4|video/mp4",
            "/immich/unique_id/asset_id/fullsize/video/mp4",
            "video/mp4",
        ),
    ],
)
async def test_resolve_media_success(
    hass: HomeAssistant, identifier: str, url: str, mime_type: str
) -> None:
    """Test successful resolving an item."""
    assert await async_setup_component(hass, "media_source", {})

    source = await async_get_media_source(hass)
    item = MediaSourceItem(hass, DOMAIN, identifier, None)
    result = await source.async_resolve_media(item)

    assert result.url == url
    assert result.mime_type == mime_type


async def test_browse_media_unconfigured(hass: HomeAssistant) -> None:
    """Test browse_media without any devices being configured."""
    assert await async_setup_component(hass, "media_source", {})

    source = await async_get_media_source(hass)
    item = MediaSourceItem(
        hass, DOMAIN, "unique_id/albums/album_id/asset_id/filename.png", None
    )
    with pytest.raises(BrowseError, match="Immich is not configured"):
        await source.async_browse_media(item)


async def test_browse_media_get_root(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browse_media returning root media sources."""
    assert await async_setup_component(hass, "media_source", {})

    with patch("homeassistant.components.immich.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry)

    source = await async_get_media_source(hass)

    # get root
    item = MediaSourceItem(hass, DOMAIN, "", None)
    result = await source.async_browse_media(item)

    assert result
    assert len(result.children) == 1
    media_file = result.children[0]
    assert isinstance(media_file, BrowseMedia)
    assert media_file.title == "Someone"
    assert media_file.media_content_id == (
        "media-source://immich/e7ef5713-9dab-4bd4-b899-715b0ca4379e"
    )

    # get collections
    item = MediaSourceItem(hass, DOMAIN, "e7ef5713-9dab-4bd4-b899-715b0ca4379e", None)
    result = await source.async_browse_media(item)

    assert result
    assert len(result.children) == 1
    media_file = result.children[0]
    assert isinstance(media_file, BrowseMedia)
    assert media_file.title == "albums"
    assert media_file.media_content_id == (
        "media-source://immich/e7ef5713-9dab-4bd4-b899-715b0ca4379e|albums"
    )


async def test_browse_media_get_albums(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browse_media returning albums."""
    assert await async_setup_component(hass, "media_source", {})

    with patch("homeassistant.components.immich.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry)

    source = await async_get_media_source(hass)
    item = MediaSourceItem(
        hass, DOMAIN, "e7ef5713-9dab-4bd4-b899-715b0ca4379e|albums", None
    )
    result = await source.async_browse_media(item)

    assert result
    assert len(result.children) == 1
    media_file = result.children[0]
    assert isinstance(media_file, BrowseMedia)
    assert media_file.title == "My Album"
    assert media_file.media_content_id == (
        "media-source://immich/"
        "e7ef5713-9dab-4bd4-b899-715b0ca4379e|albums|"
        "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6"
    )


async def test_browse_media_get_albums_error(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browse_media with unknown album."""
    assert await async_setup_component(hass, "media_source", {})

    with patch("homeassistant.components.immich.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry)

    # exception in get_albums()
    mock_immich.albums.async_get_all_albums.side_effect = ImmichError(
        {
            "message": "Not found or no album.read access",
            "error": "Bad Request",
            "statusCode": 400,
            "correlationId": "e0hlizyl",
        }
    )

    source = await async_get_media_source(hass)

    item = MediaSourceItem(hass, DOMAIN, f"{mock_config_entry.unique_id}|albums", None)
    result = await source.async_browse_media(item)

    assert result
    assert result.identifier is None
    assert len(result.children) == 0


async def test_browse_media_get_album_items_error(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browse_media returning albums."""
    assert await async_setup_component(hass, "media_source", {})

    with patch("homeassistant.components.immich.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry)

    source = await async_get_media_source(hass)

    # unknown album
    mock_immich.albums.async_get_album_info.return_value = MOCK_ALBUM_WITHOUT_ASSETS
    item = MediaSourceItem(
        hass,
        DOMAIN,
        "e7ef5713-9dab-4bd4-b899-715b0ca4379e|albums|721e1a4b-aa12-441e-8d3b-5ac7ab283bb6",
        None,
    )
    result = await source.async_browse_media(item)

    assert result
    assert result.identifier is None
    assert len(result.children) == 0

    # exception in async_get_album_info()
    mock_immich.albums.async_get_album_info.side_effect = ImmichError(
        {
            "message": "Not found or no album.read access",
            "error": "Bad Request",
            "statusCode": 400,
            "correlationId": "e0hlizyl",
        }
    )
    item = MediaSourceItem(
        hass,
        DOMAIN,
        "e7ef5713-9dab-4bd4-b899-715b0ca4379e|albums|721e1a4b-aa12-441e-8d3b-5ac7ab283bb6",
        None,
    )
    result = await source.async_browse_media(item)

    assert result
    assert result.identifier is None
    assert len(result.children) == 0


async def test_browse_media_get_album_items(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browse_media returning albums."""
    assert await async_setup_component(hass, "media_source", {})

    with patch("homeassistant.components.immich.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry)

    source = await async_get_media_source(hass)

    item = MediaSourceItem(
        hass,
        DOMAIN,
        "e7ef5713-9dab-4bd4-b899-715b0ca4379e|albums|721e1a4b-aa12-441e-8d3b-5ac7ab283bb6",
        None,
    )
    result = await source.async_browse_media(item)

    assert result
    assert len(result.children) == 2
    media_file = result.children[0]
    assert isinstance(media_file, BrowseMedia)
    assert media_file.identifier == (
        "e7ef5713-9dab-4bd4-b899-715b0ca4379e|albums|"
        "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6|"
        "2e94c203-50aa-4ad2-8e29-56dd74e0eff4|filename.jpg|image/jpeg"
    )
    assert media_file.title == "filename.jpg"
    assert media_file.media_class == MediaClass.IMAGE
    assert media_file.media_content_type == "image/jpeg"
    assert media_file.can_play is False
    assert not media_file.can_expand
    assert media_file.thumbnail == (
        "/immich/e7ef5713-9dab-4bd4-b899-715b0ca4379e/"
        "2e94c203-50aa-4ad2-8e29-56dd74e0eff4/thumbnail/image/jpeg"
    )

    media_file = result.children[1]
    assert isinstance(media_file, BrowseMedia)
    assert media_file.identifier == (
        "e7ef5713-9dab-4bd4-b899-715b0ca4379e|albums|"
        "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6|"
        "2e65a5f2-db83-44c4-81ab-f5ff20c9bd7b|filename.mp4|video/mp4"
    )
    assert media_file.title == "filename.mp4"
    assert media_file.media_class == MediaClass.VIDEO
    assert media_file.media_content_type == "video/mp4"
    assert media_file.can_play is True
    assert not media_file.can_expand
    assert media_file.thumbnail == (
        "/immich/e7ef5713-9dab-4bd4-b899-715b0ca4379e/"
        "2e65a5f2-db83-44c4-81ab-f5ff20c9bd7b/thumbnail/image/jpeg"
    )


async def test_media_view(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SynologyDsmMediaView returning albums."""
    view = ImmichMediaView(hass)
    request = MockRequest(b"", DOMAIN)

    # immich noch configured
    with pytest.raises(web.HTTPNotFound):
        await view.get(request, "", "")

    # setup immich
    assert await async_setup_component(hass, "media_source", {})
    with patch("homeassistant.components.immich.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry)

    # wrong url (without mime type)
    with pytest.raises(web.HTTPNotFound):
        await view.get(
            request,
            "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "2e94c203-50aa-4ad2-8e29-56dd74e0eff4/thumbnail",
        )

    # exception in async_view_asset()
    mock_immich.assets.async_view_asset.side_effect = ImmichError(
        {
            "message": "Not found or no asset.read access",
            "error": "Bad Request",
            "statusCode": 400,
            "correlationId": "e0hlizyl",
        }
    )
    with pytest.raises(web.HTTPNotFound):
        await view.get(
            request,
            "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "2e94c203-50aa-4ad2-8e29-56dd74e0eff4/thumbnail/image/jpeg",
        )

    # exception in async_play_video_stream()
    mock_immich.assets.async_play_video_stream.side_effect = ImmichError(
        {
            "message": "Not found or no asset.read access",
            "error": "Bad Request",
            "statusCode": 400,
            "correlationId": "e0hlizyl",
        }
    )
    with pytest.raises(web.HTTPNotFound):
        await view.get(
            request,
            "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "2e65a5f2-db83-44c4-81ab-f5ff20c9bd7b/fullsize/video/mp4",
        )

    # success
    mock_immich.assets.async_view_asset.side_effect = None
    mock_immich.assets.async_view_asset.return_value = b"xxxx"
    with patch.object(tempfile, "tempdir", tmp_path):
        result = await view.get(
            request,
            "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "2e94c203-50aa-4ad2-8e29-56dd74e0eff4/thumbnail/image/jpeg",
        )
        assert isinstance(result, web.Response)
    with patch.object(tempfile, "tempdir", tmp_path):
        result = await view.get(
            request,
            "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "2e94c203-50aa-4ad2-8e29-56dd74e0eff4/fullsize/image/jpeg",
        )
        assert isinstance(result, web.Response)

    mock_immich.assets.async_play_video_stream.side_effect = None
    mock_immich.assets.async_play_video_stream.return_value = MockStreamReaderChunked(
        b"xxxx"
    )
    with patch.object(tempfile, "tempdir", tmp_path):
        result = await view.get(
            request,
            "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "2e65a5f2-db83-44c4-81ab-f5ff20c9bd7b/fullsize/video/mp4",
        )
        assert isinstance(result, web.StreamResponse)
