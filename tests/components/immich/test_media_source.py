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
from homeassistant.components.media_player import BrowseError, BrowseMedia, MediaClass
from homeassistant.components.media_source import MediaSourceItem, Unresolvable
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.aiohttp import MockRequest, MockStreamReaderChunked

from . import setup_integration

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
    assert len(result.children) == 3

    media_file = result.children[0]
    assert isinstance(media_file, BrowseMedia)
    assert media_file.title == "albums"
    assert media_file.media_content_id == (
        "media-source://immich/e7ef5713-9dab-4bd4-b899-715b0ca4379e|albums"
    )

    media_file = result.children[1]
    assert isinstance(media_file, BrowseMedia)
    assert media_file.title == "people"
    assert media_file.media_content_id == (
        "media-source://immich/e7ef5713-9dab-4bd4-b899-715b0ca4379e|people"
    )

    media_file = result.children[2]
    assert isinstance(media_file, BrowseMedia)
    assert media_file.title == "tags"
    assert media_file.media_content_id == (
        "media-source://immich/e7ef5713-9dab-4bd4-b899-715b0ca4379e|tags"
    )


@pytest.mark.parametrize(
    ("collection", "children"),
    [
        (
            "albums",
            [{"title": "My Album", "asset_id": "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6"}],
        ),
        (
            "people",
            [
                {"title": "Me", "asset_id": "6176838a-ac5a-4d1f-9a35-91c591d962d8"},
                {"title": "I", "asset_id": "3e66aa4a-a4a8-41a4-86fe-2ae5e490078f"},
                {"title": "Myself", "asset_id": "a3c83297-684a-4576-82dc-b07432e8a18f"},
            ],
        ),
        (
            "tags",
            [
                {
                    "title": "Halloween",
                    "asset_id": "67301cb8-cb73-4e8a-99e9-475cb3f7e7b5",
                },
                {
                    "title": "Holidays",
                    "asset_id": "69bd487f-dc1e-4420-94c6-656f0515773d",
                },
            ],
        ),
    ],
)
async def test_browse_media_collections(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
    collection: str,
    children: list[dict],
) -> None:
    """Test browse through collections."""
    assert await async_setup_component(hass, "media_source", {})

    with patch("homeassistant.components.immich.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry)

    source = await async_get_media_source(hass)
    item = MediaSourceItem(
        hass, DOMAIN, f"{mock_config_entry.unique_id}|{collection}", None
    )
    result = await source.async_browse_media(item)

    assert result
    assert len(result.children) == len(children)
    for idx, child in enumerate(children):
        media_file = result.children[idx]
        assert isinstance(media_file, BrowseMedia)
        assert media_file.title == child["title"]
        assert media_file.media_content_id == (
            "media-source://immich/"
            f"{mock_config_entry.unique_id}|{collection}|"
            f"{child['asset_id']}"
        )


@pytest.mark.parametrize(
    ("collection", "mocked_get_fn"),
    [
        ("albums", ("albums", "async_get_all_albums")),
        ("people", ("people", "async_get_all_people")),
        ("tags", ("tags", "async_get_all_tags")),
    ],
)
async def test_browse_media_collections_error(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
    collection: str,
    mocked_get_fn: tuple[str, str],
) -> None:
    """Test browse_media with unknown collection."""
    assert await async_setup_component(hass, "media_source", {})

    with patch("homeassistant.components.immich.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry)

    getattr(
        getattr(mock_immich, mocked_get_fn[0]), mocked_get_fn[1]
    ).side_effect = ImmichError(
        {
            "message": "Not found or no album.read access",
            "error": "Bad Request",
            "statusCode": 400,
            "correlationId": "e0hlizyl",
        }
    )

    source = await async_get_media_source(hass)

    item = MediaSourceItem(
        hass, DOMAIN, f"{mock_config_entry.unique_id}|{collection}", None
    )
    result = await source.async_browse_media(item)

    assert result
    assert result.identifier is None
    assert len(result.children) == 0


@pytest.mark.parametrize(
    ("collection", "mocked_get_fn"),
    [
        ("albums", ("albums", "async_get_album_info")),
        ("people", ("search", "async_get_all_by_person_ids")),
        ("tags", ("search", "async_get_all_by_tag_ids")),
    ],
)
async def test_browse_media_collection_items_error(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
    collection: str,
    mocked_get_fn: tuple[str, str],
) -> None:
    """Test browse_media returning albums."""
    assert await async_setup_component(hass, "media_source", {})

    with patch("homeassistant.components.immich.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry)

    source = await async_get_media_source(hass)

    getattr(
        getattr(mock_immich, mocked_get_fn[0]), mocked_get_fn[1]
    ).side_effect = ImmichError(
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
        f"{mock_config_entry.unique_id}|{collection}|721e1a4b-aa12-441e-8d3b-5ac7ab283bb6",
        None,
    )
    result = await source.async_browse_media(item)

    assert result
    assert result.identifier is None
    assert len(result.children) == 0


@pytest.mark.parametrize(
    ("collection", "collection_id", "children"),
    [
        (
            "albums",
            "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6",
            [
                {
                    "original_file_name": "filename.jpg",
                    "asset_id": "2e94c203-50aa-4ad2-8e29-56dd74e0eff4",
                    "media_class": MediaClass.IMAGE,
                    "media_content_type": "image/jpeg",
                    "thumb_mime_type": "image/jpeg",
                    "can_play": False,
                },
                {
                    "original_file_name": "filename.mp4",
                    "asset_id": "2e65a5f2-db83-44c4-81ab-f5ff20c9bd7b",
                    "media_class": MediaClass.VIDEO,
                    "media_content_type": "video/mp4",
                    "thumb_mime_type": "image/jpeg",
                    "can_play": True,
                },
            ],
        ),
        (
            "people",
            "6176838a-ac5a-4d1f-9a35-91c591d962d8",
            [
                {
                    "original_file_name": "20250714_201122.jpg",
                    "asset_id": "2242eda3-94c2-49ee-86d4-e9e071b6fbf4",
                    "media_class": MediaClass.IMAGE,
                    "media_content_type": "image/jpeg",
                    "thumb_mime_type": "image/jpeg",
                    "can_play": False,
                },
                {
                    "original_file_name": "20250714_201121.jpg",
                    "asset_id": "046ac0d9-8acd-44d8-953f-ecb3c786358a",
                    "media_class": MediaClass.IMAGE,
                    "media_content_type": "image/jpeg",
                    "thumb_mime_type": "image/jpeg",
                    "can_play": False,
                },
            ],
        ),
        (
            "tags",
            "6176838a-ac5a-4d1f-9a35-91c591d962d8",
            [
                {
                    "original_file_name": "20110306_025024.jpg",
                    "asset_id": "ae3d82fc-beb5-4abc-ae83-11fcfa5e7629",
                    "media_class": MediaClass.IMAGE,
                    "media_content_type": "image/jpeg",
                    "thumb_mime_type": "image/jpeg",
                    "can_play": False,
                },
                {
                    "original_file_name": "20110306_024053.jpg",
                    "asset_id": "b71d0d08-6727-44ae-8bba-83c190f95df4",
                    "media_class": MediaClass.IMAGE,
                    "media_content_type": "image/jpeg",
                    "thumb_mime_type": "image/jpeg",
                    "can_play": False,
                },
            ],
        ),
    ],
)
async def test_browse_media_collection_get_items(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
    collection: str,
    collection_id: str,
    children: list[dict],
) -> None:
    """Test browse_media returning albums."""
    assert await async_setup_component(hass, "media_source", {})

    with patch("homeassistant.components.immich.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry)

    source = await async_get_media_source(hass)

    item = MediaSourceItem(
        hass,
        DOMAIN,
        f"{mock_config_entry.unique_id}|{collection}|{collection_id}",
        None,
    )
    result = await source.async_browse_media(item)

    assert result
    assert len(result.children) == len(children)

    for idx, child in enumerate(children):
        media_file = result.children[idx]
        assert isinstance(media_file, BrowseMedia)
        assert media_file.identifier == (
            f"{mock_config_entry.unique_id}|{collection}|{collection_id}|"
            f"{child['asset_id']}|{child['original_file_name']}|{child['media_content_type']}"
        )
        assert media_file.title == child["original_file_name"]
        assert media_file.media_class == child["media_class"]
        assert media_file.media_content_type == child["media_content_type"]
        assert media_file.can_play is child["can_play"]
        assert not media_file.can_expand
        assert media_file.thumbnail == (
            f"/immich/{mock_config_entry.unique_id}/"
            f"{child['asset_id']}/thumbnail/{child['thumb_mime_type']}"
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

    # exception in async_get_person_thumbnail()
    mock_immich.people.async_get_person_thumbnail.side_effect = ImmichError(
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
            "2e94c203-50aa-4ad2-8e29-56dd74e0eff4/person/image/jpeg",
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

    mock_immich.people.async_get_person_thumbnail.side_effect = None
    mock_immich.people.async_get_person_thumbnail.return_value = b"xxxx"
    with patch.object(tempfile, "tempdir", tmp_path):
        result = await view.get(
            request,
            "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "2e94c203-50aa-4ad2-8e29-56dd74e0eff4/person/image/jpeg",
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
