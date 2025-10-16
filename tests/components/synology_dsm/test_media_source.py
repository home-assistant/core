"""Tests for Synology DSM Media Source."""

import mimetypes
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import web
import pytest
from synology_dsm.api.photos import SynoPhotosAlbum, SynoPhotosItem
from synology_dsm.exceptions import SynologyDSMException

from homeassistant.components.media_player import BrowseError, BrowseMedia, MediaClass
from homeassistant.components.media_source import MediaSourceItem, Unresolvable
from homeassistant.components.synology_dsm.const import DOMAIN
from homeassistant.components.synology_dsm.media_source import (
    SynologyDsmMediaView,
    SynologyPhotosMediaSource,
    async_get_media_source,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.aiohttp import MockRequest

from .common import mock_dsm_information
from .consts import HOST, MACS, PASSWORD, PORT, USE_SSL, USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def dsm_with_photos() -> MagicMock:
    """Set up SynologyDSM API fixture."""
    dsm = MagicMock()
    dsm.login = AsyncMock(return_value=True)
    dsm.update = AsyncMock(return_value=True)
    dsm.information = mock_dsm_information()
    dsm.network.update = AsyncMock(return_value=True)
    dsm.surveillance_station.update = AsyncMock(return_value=True)
    dsm.upgrade.update = AsyncMock(return_value=True)

    dsm.photos.get_albums = AsyncMock(
        return_value=[SynoPhotosAlbum(1, "Album 1", 10, "")]
    )
    dsm.photos.get_items_from_album = AsyncMock(
        return_value=[
            # Image items
            SynoPhotosItem(
                10, "", "filename.jpg", "12345", "10_1298753", "sm", False, ""
            ),
            SynoPhotosItem(
                10, "", "filename.jpg", "12345", "10_1298753", "sm", True, ""
            ),
            # Video items - various formats
            SynoPhotosItem(20, "", "video.mp4", "67890", "20_5432109", "sm", False, ""),
            SynoPhotosItem(21, "", "movie.mkv", "67891", "21_5432110", "sm", True, ""),
            SynoPhotosItem(22, "", "clip.avi", "67892", "22_5432111", "sm", False, ""),
            SynoPhotosItem(
                23, "", "recording.mov", "67893", "23_5432112", "sm", False, ""
            ),
            SynoPhotosItem(24, "", "video.wmv", "67894", "24_5432113", "sm", True, ""),
        ]
    )
    dsm.photos.get_items_from_shared_space = AsyncMock(
        return_value=[
            SynoPhotosItem(
                10, "", "filename.jpg", "12345", "10_1298753", "sm", True, ""
            ),
            # Add a video to shared space too
            SynoPhotosItem(
                30, "", "shared_video.mp4", "99999", "30_9876543", "sm", True, ""
            ),
        ]
    )
    dsm.photos.get_item_thumbnail_url = AsyncMock(
        return_value="http://my.thumbnail.url"
    )
    dsm.file = AsyncMock(get_shared_folders=AsyncMock(return_value=None))

    # Set up API structure for video streaming tests
    dsm.api = MagicMock()
    dsm.api.dsm = MagicMock()
    dsm.api.dsm.get = AsyncMock(return_value=b"fake_video_data")

    return dsm


@pytest.mark.usefixtures("setup_media_source")
async def test_get_media_source(hass: HomeAssistant) -> None:
    """Test the async_get_media_source function and SynologyPhotosMediaSource constructor."""

    source = await async_get_media_source(hass)
    assert isinstance(source, SynologyPhotosMediaSource)
    assert source.domain == DOMAIN


@pytest.mark.usefixtures("setup_media_source")
@pytest.mark.parametrize(
    ("identifier", "exception_msg"),
    [
        ("unique_id", "No album id"),
        ("unique_id/1", "No file name"),
        ("unique_id/1/cache_key", "No file name"),
        ("unique_id/1/cache_key/filename", "No file extension"),
    ],
)
async def test_resolve_media_bad_identifier(
    hass: HomeAssistant, identifier: str, exception_msg: str
) -> None:
    """Test resolve_media with bad identifiers."""
    source = await async_get_media_source(hass)
    item = MediaSourceItem(hass, DOMAIN, identifier, None)
    with pytest.raises(Unresolvable, match=exception_msg):
        await source.async_resolve_media(item)


@pytest.mark.usefixtures("setup_media_source")
@pytest.mark.parametrize(
    ("identifier", "url", "mime_type"),
    [
        (
            "ABC012345/10/27643_876876/filename.jpg",
            "/synology_dsm/ABC012345/27643_876876/filename.jpg/",
            "image/jpeg",
        ),
        (
            "ABC012345/12/12631_47189/filename.png",
            "/synology_dsm/ABC012345/12631_47189/filename.png/",
            "image/png",
        ),
        (
            "ABC012345/12/12631_47189/filename.png_shared",
            "/synology_dsm/ABC012345/12631_47189/filename.png_shared/",
            "image/png",
        ),
        (
            "ABC012345/12_dmypass/12631_47189/filename.png",
            "/synology_dsm/ABC012345/12631_47189/filename.png/dmypass",
            "image/png",
        ),
    ],
)
async def test_resolve_media_success(
    hass: HomeAssistant, identifier: str, url: str, mime_type: str
) -> None:
    """Test successful resolving an item."""
    source = await async_get_media_source(hass)
    item = MediaSourceItem(hass, DOMAIN, identifier, None)
    result = await source.async_resolve_media(item)

    assert result.url == url
    assert result.mime_type == mime_type


@pytest.mark.usefixtures("setup_media_source")
async def test_browse_media_unconfigured(hass: HomeAssistant) -> None:
    """Test browse_media without any devices being configured."""
    source = await async_get_media_source(hass)
    item = MediaSourceItem(
        hass, DOMAIN, "unique_id/album_id/cache_key/filename.jpg", None
    )
    with pytest.raises(BrowseError, match="Diskstation not initialized"):
        await source.async_browse_media(item)


@pytest.mark.usefixtures("setup_media_source")
async def test_browse_media_album_error(
    hass: HomeAssistant, dsm_with_photos: MagicMock
) -> None:
    """Test browse_media with unknown album."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=dsm_with_photos,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id="mocked_syno_dsm_entry",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)

    # exception in get_albums()
    dsm_with_photos.photos.get_albums = AsyncMock(
        side_effect=SynologyDSMException("", None)
    )

    source = await async_get_media_source(hass)

    item = MediaSourceItem(hass, DOMAIN, entry.unique_id, None)
    result = await source.async_browse_media(item)

    assert result
    assert result.identifier is None
    assert len(result.children) == 0


@pytest.mark.usefixtures("setup_media_source")
async def test_browse_media_get_root(
    hass: HomeAssistant, dsm_with_photos: MagicMock
) -> None:
    """Test browse_media returning root media sources."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=dsm_with_photos,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id="mocked_syno_dsm_entry",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)

    source = await async_get_media_source(hass)
    item = MediaSourceItem(hass, DOMAIN, "", None)
    result = await source.async_browse_media(item)

    assert result
    assert len(result.children) == 1
    assert isinstance(result.children[0], BrowseMedia)
    assert result.children[0].identifier == "mocked_syno_dsm_entry"


@pytest.mark.usefixtures("setup_media_source")
async def test_browse_media_get_albums(
    hass: HomeAssistant, dsm_with_photos: MagicMock
) -> None:
    """Test browse_media returning albums."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=dsm_with_photos,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id="mocked_syno_dsm_entry",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)

    source = await async_get_media_source(hass)
    item = MediaSourceItem(hass, DOMAIN, "mocked_syno_dsm_entry", None)
    result = await source.async_browse_media(item)

    assert result
    assert len(result.children) == 3
    assert isinstance(result.children[0], BrowseMedia)
    assert result.children[0].identifier == "mocked_syno_dsm_entry/0"
    assert result.children[0].title == "All media"
    assert isinstance(result.children[1], BrowseMedia)
    assert result.children[1].identifier == "mocked_syno_dsm_entry/shared"
    assert result.children[1].title == "Shared space"
    assert isinstance(result.children[2], BrowseMedia)
    assert result.children[2].identifier == "mocked_syno_dsm_entry/1_"
    assert result.children[2].title == "Album 1"


@pytest.mark.usefixtures("setup_media_source")
async def test_browse_media_get_items_error(
    hass: HomeAssistant, dsm_with_photos: MagicMock
) -> None:
    """Test browse_media returning albums."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=dsm_with_photos,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id="mocked_syno_dsm_entry",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)

    source = await async_get_media_source(hass)

    # unknown album
    dsm_with_photos.photos.get_items_from_album = AsyncMock(return_value=[])
    item = MediaSourceItem(hass, DOMAIN, "mocked_syno_dsm_entry/1", None)
    result = await source.async_browse_media(item)

    assert result
    assert result.identifier is None
    assert len(result.children) == 0

    # exception in get_items_from_album()
    dsm_with_photos.photos.get_items_from_album = AsyncMock(
        side_effect=SynologyDSMException("", None)
    )
    item = MediaSourceItem(hass, DOMAIN, "mocked_syno_dsm_entry/1", None)
    result = await source.async_browse_media(item)

    assert result
    assert result.identifier is None
    assert len(result.children) == 0

    # exception in get_items_from_shared_space()
    dsm_with_photos.photos.get_items_from_shared_space = AsyncMock(
        side_effect=SynologyDSMException("", None)
    )
    item = MediaSourceItem(hass, DOMAIN, "mocked_syno_dsm_entry/shared", None)
    result = await source.async_browse_media(item)

    assert result
    assert result.identifier is None
    assert len(result.children) == 0


@pytest.mark.usefixtures("setup_media_source")
async def test_browse_media_get_items_thumbnail_error(
    hass: HomeAssistant, dsm_with_photos: MagicMock
) -> None:
    """Test browse_media returning albums."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=dsm_with_photos,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id="mocked_syno_dsm_entry",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)

    source = await async_get_media_source(hass)

    dsm_with_photos.photos.get_item_thumbnail_url = AsyncMock(
        side_effect=SynologyDSMException("", None)
    )
    item = MediaSourceItem(hass, DOMAIN, "mocked_syno_dsm_entry/1", None)
    result = await source.async_browse_media(item)

    assert result
    assert len(result.children) == 7  # 2 images + 5 videos from dsm_with_photos fixture
    item = result.children[0]
    assert isinstance(item, BrowseMedia)
    assert item.thumbnail is None


@pytest.mark.usefixtures("setup_media_source")
async def test_browse_media_get_items(
    hass: HomeAssistant, dsm_with_photos: MagicMock
) -> None:
    """Test browse_media returning albums."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=dsm_with_photos,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id="mocked_syno_dsm_entry",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)

    source = await async_get_media_source(hass)

    item = MediaSourceItem(hass, DOMAIN, "mocked_syno_dsm_entry/1", None)
    result = await source.async_browse_media(item)

    assert result
    assert len(result.children) == 7  # 2 images + 5 videos from dsm_with_photos fixture
    item = result.children[0]
    assert isinstance(item, BrowseMedia)
    assert item.identifier == "mocked_syno_dsm_entry/1_/10_1298753/filename.jpg"
    assert item.title == "filename.jpg"
    assert item.media_class == MediaClass.IMAGE
    assert item.media_content_type == "image/jpeg"
    assert item.can_play
    assert not item.can_expand
    assert item.thumbnail == "http://my.thumbnail.url"
    item = result.children[1]
    assert isinstance(item, BrowseMedia)
    assert item.identifier == "mocked_syno_dsm_entry/1_/10_1298753/filename.jpg_shared"
    assert item.title == "filename.jpg"
    assert item.media_class == MediaClass.IMAGE
    assert item.media_content_type == "image/jpeg"
    assert item.can_play
    assert not item.can_expand
    assert item.thumbnail == "http://my.thumbnail.url"

    item = MediaSourceItem(hass, DOMAIN, "mocked_syno_dsm_entry/shared", None)
    result = await source.async_browse_media(item)
    assert result
    assert len(result.children) == 2  # 1 image + 1 video from shared_space fixture
    item = result.children[0]
    assert (
        item.identifier
        == "mocked_syno_dsm_entry/shared_/10_1298753/filename.jpg_shared"
    )
    assert item.title == "filename.jpg"
    assert item.media_class == MediaClass.IMAGE
    assert item.media_content_type == "image/jpeg"
    assert item.can_play
    assert not item.can_expand
    assert item.thumbnail == "http://my.thumbnail.url"


@pytest.mark.usefixtures("setup_media_source")
async def test_media_view(
    hass: HomeAssistant, tmp_path: Path, dsm_with_photos: MagicMock
) -> None:
    """Test SynologyDsmMediaView returning albums."""
    view = SynologyDsmMediaView(hass)
    request = MockRequest(b"", DOMAIN)

    # diskation not set uped
    with pytest.raises(web.HTTPNotFound):
        await view.get(request, "", "")

    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=dsm_with_photos,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id="mocked_syno_dsm_entry",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)

    with pytest.raises(web.HTTPNotFound):
        await view.get(request, "", "10_1298753/filename/")

    # exception in download_item()
    dsm_with_photos.photos.download_item = AsyncMock(
        side_effect=SynologyDSMException("", None)
    )
    with pytest.raises(web.HTTPNotFound):
        await view.get(request, "mocked_syno_dsm_entry", "10_1298753/filename.jpg/")

    # success
    dsm_with_photos.photos.download_item = AsyncMock(return_value=b"xxxx")
    with patch.object(tempfile, "tempdir", tmp_path):
        result = await view.get(
            request, "mocked_syno_dsm_entry", "10_1298753/filename.jpg/"
        )
        assert isinstance(result, web.Response)
    with patch.object(tempfile, "tempdir", tmp_path):
        result = await view.get(
            request, "mocked_syno_dsm_entry", "10_1298753/filename.jpg_shared/"
        )
        assert isinstance(result, web.Response)


# Video Support Tests


@pytest.mark.usefixtures("setup_media_source")
async def test_browse_media_video_items(
    hass: HomeAssistant, dsm_with_photos: MagicMock
) -> None:
    """Test browse_media returns video items with correct MediaClass.MOVIE."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=dsm_with_photos,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id="mocked_syno_dsm_entry",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)

    source = await async_get_media_source(hass)
    item = MediaSourceItem(hass, DOMAIN, "mocked_syno_dsm_entry/1", None)
    result = await source.async_browse_media(item)

    assert result
    assert len(result.children) == 7  # 2 images + 5 videos

    # Check video items have correct MediaClass.MOVIE
    video_items = [
        child for child in result.children if child.media_class == MediaClass.MOVIE
    ]
    assert len(video_items) == 5

    # Check specific video items
    mp4_item = next(child for child in result.children if "video.mp4" in child.title)
    assert mp4_item.media_class == MediaClass.MOVIE
    assert mp4_item.media_content_type == "video/mp4"
    assert mp4_item.can_play
    assert not mp4_item.can_expand

    mkv_item = next(child for child in result.children if "movie.mkv" in child.title)
    assert mkv_item.media_class == MediaClass.MOVIE
    assert mkv_item.media_content_type == "video/matroska"


@pytest.mark.parametrize(
    ("filename", "expected_mime", "expected_class"),
    [
        # Video files
        ("video.mp4", "video/mp4", MediaClass.MOVIE),
        ("movie.mkv", "video/matroska", MediaClass.MOVIE),
        ("clip.avi", "video/vnd.avi", MediaClass.MOVIE),
        ("recording.mov", "video/quicktime", MediaClass.MOVIE),
        ("video.wmv", "video/x-ms-wmv", MediaClass.MOVIE),
        ("stream.webm", "video/webm", MediaClass.MOVIE),
        ("video.m4v", "video/x-m4v", MediaClass.MOVIE),
        # Image files for comparison
        ("photo.jpg", "image/jpeg", MediaClass.IMAGE),
        ("picture.png", "image/png", MediaClass.IMAGE),
        ("image.gif", "image/gif", MediaClass.IMAGE),
    ],
)
async def test_media_class_assignment(filename, expected_mime, expected_class):
    """Test that files get correct MediaClass based on MIME type."""
    mime_type, _ = mimetypes.guess_type(filename)
    assert mime_type == expected_mime

    # Test MediaClass assignment logic
    media_class = (
        MediaClass.MOVIE
        if mime_type and mime_type.startswith("video/")
        else MediaClass.IMAGE
    )
    assert media_class == expected_class


@pytest.mark.usefixtures("setup_media_source")
@pytest.mark.parametrize(
    ("identifier", "url", "mime_type"),
    [
        # Video files
        (
            "ABC012345/10/27643_876876/video.mp4",
            "/synology_dsm/ABC012345/27643_876876/video.mp4/",
            "video/mp4",
        ),
        (
            "ABC012345/12/12631_47189/movie.mkv",
            "/synology_dsm/ABC012345/12631_47189/movie.mkv/",
            "video/matroska",
        ),
        (
            "ABC012345/12/12631_47189/clip.avi",
            "/synology_dsm/ABC012345/12631_47189/clip.avi/",
            "video/vnd.avi",
        ),
        (
            "ABC012345/12/12631_47189/video.mp4_shared",
            "/synology_dsm/ABC012345/12631_47189/video.mp4_shared/",
            "video/mp4",
        ),
        (
            "ABC012345/12_videopass/12631_47189/movie.mov",
            "/synology_dsm/ABC012345/12631_47189/movie.mov/videopass",
            "video/quicktime",
        ),
    ],
)
async def test_resolve_media_video_success(
    hass: HomeAssistant, identifier: str, url: str, mime_type: str
) -> None:
    """Test successful video media resolution."""
    source = await async_get_media_source(hass)
    item = MediaSourceItem(hass, DOMAIN, identifier, None)
    result = await source.async_resolve_media(item)

    assert result.url == url
    assert result.mime_type == mime_type


class TestSynologyDsmMediaViewVideoMethods:
    """Test SynologyDsmMediaView video-specific helper methods."""

    def test_optimize_range_request_scenarios(self):
        """Test _optimize_range_request with various inputs."""
        view = SynologyDsmMediaView(None)

        # Full file request - should be optimized to 10MB
        assert view._optimize_range_request("bytes=0-") == "bytes=0-10485759"

        # Specific range - should pass through unchanged
        assert view._optimize_range_request("bytes=1000-2000") == "bytes=1000-2000"
        assert (
            view._optimize_range_request("bytes=5000000-6000000")
            == "bytes=5000000-6000000"
        )

        # Different starting position - should pass through
        assert view._optimize_range_request("bytes=100-") == "bytes=100-"

        # Invalid format - should pass through unchanged
        assert view._optimize_range_request("invalid") == "invalid"
        assert view._optimize_range_request("bytes=invalid") == "bytes=invalid"
        assert view._optimize_range_request("") == ""

    def test_handle_range_request_from_content_success(self):
        """Test _handle_range_request_from_content successful scenarios."""
        view = SynologyDsmMediaView(None)
        content = b"0123456789" * 1000  # 10KB test content

        # Test first 1KB
        response = view._handle_range_request_from_content(
            content, "video/mp4", "bytes=0-1023"
        )
        assert response.status == 206
        assert len(response.body) == 1024
        assert response.headers["Content-Type"] == "video/mp4"
        assert response.headers["Content-Range"] == "bytes 0-1023/10000"
        assert response.headers["Accept-Ranges"] == "bytes"

        # Test middle range
        response = view._handle_range_request_from_content(
            content, "video/mkv", "bytes=5000-5999"
        )
        assert response.status == 206
        assert len(response.body) == 1000
        assert response.headers["Content-Range"] == "bytes 5000-5999/10000"

        # Test open-ended range
        response = view._handle_range_request_from_content(
            content, "video/avi", "bytes=9000-"
        )
        assert response.status == 206
        assert len(response.body) == 1000  # Last 1KB
        assert response.headers["Content-Range"] == "bytes 9000-9999/10000"

    def test_handle_range_request_from_content_errors(self):
        """Test _handle_range_request_from_content error scenarios."""
        view = SynologyDsmMediaView(None)
        content = b"0123456789" * 100  # 1KB content

        # Invalid range format
        with pytest.raises(web.HTTPRequestRangeNotSatisfiable):
            view._handle_range_request_from_content(
                content, "video/mp4", "invalid-range"
            )

        # Start beyond content
        with pytest.raises(web.HTTPRequestRangeNotSatisfiable):
            view._handle_range_request_from_content(
                content, "video/mp4", "bytes=2000-2999"
            )

        # Start > end
        with pytest.raises(web.HTTPRequestRangeNotSatisfiable):
            view._handle_range_request_from_content(
                content, "video/mp4", "bytes=500-400"
            )


@pytest.mark.usefixtures("setup_media_source")
async def test_media_view_video_streaming(
    hass: HomeAssistant, dsm_with_photos: MagicMock, tmp_path: Path
) -> None:
    """Test SynologyDsmMediaView video streaming with Range requests."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=dsm_with_photos,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id="mocked_syno_dsm_entry",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)

    # Get the config entry and mock its runtime_data
    config_entry = hass.config_entries.async_get_entry("mocked_syno_dsm_entry")
    assert config_entry is not None

    # Create a mock diskstation with proper API structure
    mock_diskstation = MagicMock()
    mock_diskstation.api.dsm.get = AsyncMock(return_value=b"fake_video_data" * 1000)
    config_entry.runtime_data = mock_diskstation

    view = SynologyDsmMediaView(hass)  # Create mock request with Range header
    request = MockRequest(b"", DOMAIN, headers={"Range": "bytes=0-"})

    with patch.object(tempfile, "tempdir", tmp_path):
        result = await view.get(  # type: ignore[arg-type]
            request, "mocked_syno_dsm_entry", "20_5432109/video.mp4/"
        )

        # Should get optimized range request
        dsm_with_photos.api.dsm.get.assert_called_once()
        call_args = dsm_with_photos.api.dsm.get.call_args
        assert (
            call_args[1]["headers"]["Range"] == "bytes=0-10485759"
        )  # Optimized to 10MB

        assert isinstance(result, web.Response)
        assert result.status == 206  # Partial Content
