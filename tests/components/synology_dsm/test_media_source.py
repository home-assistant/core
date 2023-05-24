"""Tests for Synology DSM Media Source."""

from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from synology_dsm.api.photos import SynoPhotosAlbum, SynoPhotosItem
from synology_dsm.exceptions import SynologyDSMException

from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_source import (
    BrowseError,
    BrowseMedia,
    MediaSourceItem,
    Unresolvable,
)
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
from homeassistant.util.aiohttp import MockRequest, web

from .consts import HOST, MACS, PASSWORD, PORT, USE_SSL, USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def dsm_with_photos() -> MagicMock:
    """Set up SynologyDSM API fixture."""
    dsm = MagicMock()
    dsm.login = AsyncMock(return_value=True)
    dsm.update = AsyncMock(return_value=True)
    dsm.network.update = AsyncMock(return_value=True)
    dsm.surveillance_station.update = AsyncMock(return_value=True)
    dsm.upgrade.update = AsyncMock(return_value=True)

    dsm.photos.get_albums = AsyncMock(return_value=[SynoPhotosAlbum(1, "Album 1", 10)])
    dsm.photos.get_items_from_album = AsyncMock(
        return_value=[SynoPhotosItem(10, "", "filename.jpg", 12345, "10_1298753", "sm")]
    )
    dsm.photos.get_item_thumbnail_url = AsyncMock(
        return_value="http://my.thumbnail.url"
    )
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
            "/synology_dsm/ABC012345/27643_876876/filename.jpg",
            "image/jpeg",
        ),
        (
            "ABC012345/12/12631_47189/filename.png",
            "/synology_dsm/ABC012345/12631_47189/filename.png",
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
    with patch(
        "homeassistant.components.synology_dsm.common.SynologyDSM",
        return_value=dsm_with_photos,
    ), patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]):
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
    with patch(
        "homeassistant.components.synology_dsm.common.SynologyDSM",
        return_value=dsm_with_photos,
    ), patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]):
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
    with patch(
        "homeassistant.components.synology_dsm.common.SynologyDSM",
        return_value=dsm_with_photos,
    ), patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]):
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
    assert len(result.children) == 2
    assert isinstance(result.children[0], BrowseMedia)
    assert result.children[0].identifier == "mocked_syno_dsm_entry/0"
    assert result.children[0].title == "All images"
    assert isinstance(result.children[1], BrowseMedia)
    assert result.children[1].identifier == "mocked_syno_dsm_entry/1"
    assert result.children[1].title == "Album 1"


@pytest.mark.usefixtures("setup_media_source")
async def test_browse_media_get_items_error(
    hass: HomeAssistant, dsm_with_photos: MagicMock
) -> None:
    """Test browse_media returning albums."""
    with patch(
        "homeassistant.components.synology_dsm.common.SynologyDSM",
        return_value=dsm_with_photos,
    ), patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]):
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


@pytest.mark.usefixtures("setup_media_source")
async def test_browse_media_get_items_thumbnail_error(
    hass: HomeAssistant, dsm_with_photos: MagicMock
) -> None:
    """Test browse_media returning albums."""
    with patch(
        "homeassistant.components.synology_dsm.common.SynologyDSM",
        return_value=dsm_with_photos,
    ), patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]):
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
    assert len(result.children) == 1
    item = result.children[0]
    assert isinstance(item, BrowseMedia)
    assert item.thumbnail is None


@pytest.mark.usefixtures("setup_media_source")
async def test_browse_media_get_items(
    hass: HomeAssistant, dsm_with_photos: MagicMock
) -> None:
    """Test browse_media returning albums."""
    with patch(
        "homeassistant.components.synology_dsm.common.SynologyDSM",
        return_value=dsm_with_photos,
    ), patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]):
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
    assert len(result.children) == 1
    item = result.children[0]
    assert isinstance(item, BrowseMedia)
    assert item.identifier == "mocked_syno_dsm_entry/1/10_1298753/filename.jpg"
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

    with patch(
        "homeassistant.components.synology_dsm.common.SynologyDSM",
        return_value=dsm_with_photos,
    ), patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]):
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
        await view.get(request, "", "10_1298753/filename")

    # exception in download_item()
    dsm_with_photos.photos.download_item = AsyncMock(
        side_effect=SynologyDSMException("", None)
    )
    with pytest.raises(web.HTTPNotFound):
        await view.get(request, "mocked_syno_dsm_entry", "10_1298753/filename.jpg")

    # success
    dsm_with_photos.photos.download_item = AsyncMock(return_value=b"xxxx")
    tempfile.tempdir = tmp_path
    result = await view.get(request, "mocked_syno_dsm_entry", "10_1298753/filename.jpg")
    assert isinstance(result, web.Response)
