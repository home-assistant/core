"""Tests for media source of the iCloud integration."""

from base64 import b64encode
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch
import urllib.parse

from aiohttp import hdrs
import pytest

from homeassistant.components.icloud.const import DOMAIN
from homeassistant.components.icloud.media_source import PhotoCache
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    URI_SCHEME,
    BrowseMediaSource,
    Unresolvable,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import AsyncMock, MockConfigEntry
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
    """Setup media source component."""

    await async_setup_component(hass, "media_source", {})


@pytest.mark.parametrize(
    ("url", "title", "media_class", "children"),
    [
        (
            f"{URI_SCHEME}{DOMAIN}",
            "iCloud Media",
            MediaClass.DIRECTORY,
            1,
        ),
        (
            f"{URI_SCHEME}{DOMAIN}/test_account_id",
            "iCloud Media / Test iCloud Account",
            MediaClass.DIRECTORY,
            2,
        ),
        (
            f"{URI_SCHEME}{DOMAIN}/test_account_id/album",
            "iCloud Media / Test iCloud Account / Albums",
            MediaClass.DIRECTORY,
            2,
        ),
        (
            f"{URI_SCHEME}{DOMAIN}/test_account_id/album/album_id1",
            "iCloud Media / Test iCloud Account / Albums / All Photos",
            MediaClass.DIRECTORY,
            3,
        ),
        (
            f"{URI_SCHEME}{DOMAIN}/test_account_id/shared",
            "iCloud Media / Test iCloud Account / Shared Streams",
            MediaClass.DIRECTORY,
            2,
        ),
        (
            f"{URI_SCHEME}{DOMAIN}/test_account_id/shared/stream_id1",
            "iCloud Media / Test iCloud Account / Shared Streams / Favorites",
            MediaClass.DIRECTORY,
            2,
        ),
    ],
    ids=[
        "root",
        "account",
        "albums",
        "album_photos",
        "shared_streams",
        "shared_stream_photos",
    ],
)
@pytest.mark.usefixtures("icloud_client")
async def test_browse_media(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    url: str,
    title: str,
    media_class: str,
    children: int,
) -> None:
    """Test browsing media."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    browse: BrowseMediaSource = await async_browse_media(hass, url)
    assert browse.title == title
    assert browse.media_class == media_class
    assert browse.children is not None
    assert len(browse.children) == children


@pytest.mark.usefixtures("icloud_client")
async def test_browse_media_accounts(
    hass: HomeAssistant,
) -> None:
    """Test browsing media with multiple accounts."""

    config_entry_1 = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_account_id_1",
        title="Test iCloud Account 1",
        data={
            "username": "test_user_1",
            "password": "test_pass_1",
            "with_family": False,
            "max_interval": 0,
            "gps_accuracy_threshold": 0,
        },
    )

    config_entry_1.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_1.entry_id)
    await hass.async_block_till_done()

    assert config_entry_1.state is ConfigEntryState.LOADED

    config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_account_id_2",
        title="Test iCloud Account 2",
        data={
            "username": "test_user_2",
            "password": "test_pass_2",
            "with_family": True,
            "max_interval": 0,
            "gps_accuracy_threshold": 0,
        },
    )

    config_entry_2.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_2.entry_id)
    await hass.async_block_till_done()

    assert config_entry_2.state is ConfigEntryState.LOADED

    assert len(hass.config_entries.async_loaded_entries(DOMAIN)) == 2

    browse: BrowseMediaSource = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.title == "iCloud Media"
    assert browse.media_class == MediaClass.DIRECTORY
    assert browse.children is not None
    assert len(browse.children) == 2


@pytest.mark.parametrize(
    ("media_content_id", "service", "has_value", "exception"),
    [
        (
            "/invalid_account_id",
            None,
            None,
            Unresolvable,
        ),
        (
            "/test_account_id/invalid_view",
            None,
            None,
            Unresolvable,
        ),
        (
            "/test_account_id/album/invalid_album_id",
            None,
            None,
            Unresolvable,
        ),
        (
            "/test_account_id/shared/invalid_album_id",
            None,
            None,
            Unresolvable,
        ),
        (
            "/test_account_id/album",
            "api",
            False,
            BrowseError,
        ),
        (
            "/test_account_id/album",
            "api.photos",
            False,
            Exception,
        ),
        (
            "/test_account_id/shared",
            "api",
            False,
            BrowseError,
        ),
        (
            "/test_account_id/shared",
            "api.photos",
            False,
            Exception,
        ),
        (
            "/test_account_id/album",
            "api.photos.albums",
            True,
            Exception,
        ),
        (
            "/test_account_id/shared",
            "api.photos.shared_streams",
            True,
            Exception,
        ),
        (
            "/test_account_id/shared/stream_id1",
            "api.photos.shared_streams.get",
            None,
            Exception,
        ),
        (
            "/test_account_id/album/stream_id1",
            "api.photos.albums.get",
            None,
            Exception,
        ),
    ],
    ids=[
        "invalid_account_id",
        "invalid_view",
        "invalid_album_id_in_album_view",
        "invalid_album_id_in_shared_view",
        "api_not_available_for_album_view",
        "photos_not_available_for_album_view",
        "api_not_available_for_shared_view",
        "photos_not_available_for_shared_view",
        "albums_not_available_for_album_view",
        "shared_streams_not_available_for_shared_view",
        "stream_not_available_for_shared_stream",
        "album_not_available_for_album",
    ],
)
async def test_browse_media_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    icloud_client: AsyncMock,
    media_content_id: str,
    service: str,
    has_value: bool,
    exception: type[Exception],
) -> None:
    """Test browsing media with exceptions."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    if service and exception:
        parent = icloud_client
        properties = service.split(".")

        while len(properties) > 1:
            prop = properties.pop(0)
            p_mock = PropertyMock()
            setattr(parent, prop, p_mock)
            parent = p_mock
        setattr(
            parent,
            properties[0],
            None if not has_value else PropertyMock(side_effect=exception()),
        )

    with pytest.raises(exception):
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}{media_content_id}")


@pytest.mark.usefixtures("icloud_client")
async def test_browse_media_not_initialized_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test browsing media with account not initialized."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    config_entry.runtime_data = None

    with pytest.raises(Unresolvable, match="Account not initialized: test_account_id"):
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/test_account_id")


@pytest.mark.usefixtures("icloud_client")
async def test_browse_media_item_is_leaf(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test browsing media with item that is a leaf node."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(BrowseError, match="Unknown media item"):
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/test_account_id/album/album_id1/photo_id1"
        )


@pytest.mark.usefixtures("icloud_client")
async def test_browse_media_not_configured_exception(
    hass: HomeAssistant,
) -> None:
    """Test browsing media with no account configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_account_id",
        title="Test iCloud Account",
        data={
            "username": "test_user",
            "password": "test_pass",
            "with_family": False,
            "max_interval": 0,
            "gps_accuracy_threshold": 0,
        },
        disabled_by=ConfigEntryDisabler.USER,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(BrowseError, match="Config entry not loaded"):
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")


@pytest.mark.parametrize(
    ("media_content_id", "url", "mime_type"),
    [
        (
            "/test_account_id/album/album_id1/photo_id1",
            "/api/icloud/media_source/serve/original/dGVzdF9hY2NvdW50X2lkL2FsYnVtL2FsYnVtX2lkMS9waG90b19pZDE=",
            "image/jpeg",
        ),
        (
            "/test_account_id/album/album_id2/photo_id2",
            "/api/icloud/media_source/serve/original/dGVzdF9hY2NvdW50X2lkL2FsYnVtL2FsYnVtX2lkMi9waG90b19pZDI=",
            "image/heic",
        ),
        (
            "/test_account_id/album/album_id1/photo_id3",
            "/api/icloud/media_source/serve/original/dGVzdF9hY2NvdW50X2lkL2FsYnVtL2FsYnVtX2lkMS9waG90b19pZDM=",
            "image/png",
        ),
        (
            "/test_account_id/shared/stream_id1/shared_id1",
            "/api/icloud/media_source/serve/original/dGVzdF9hY2NvdW50X2lkL3NoYXJlZC9zdHJlYW1faWQxL3NoYXJlZF9pZDE=",
            "image/jpeg",
        ),
        (
            "/test_account_id/shared/stream_id1/shared_id2",
            "/api/icloud/media_source/serve/original/dGVzdF9hY2NvdW50X2lkL3NoYXJlZC9zdHJlYW1faWQxL3NoYXJlZF9pZDI=",
            "video/mp4",
        ),
    ],
    ids=[
        "album_1_photo_jpeg",
        "album_2_photo_heic",
        "album_3_photo_png",
        "shared_stream_photo",
        "shared_stream_movie",
    ],
)
@pytest.mark.usefixtures("icloud_client")
async def test_resolve_media(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    media_content_id: str,
    url: str,
    mime_type: str,
) -> None:
    """Test resolving media."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    media = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}{media_content_id}",
        None,
    )
    assert media.url == url
    assert media.mime_type == mime_type


@pytest.mark.parametrize(
    ("media_content_id", "exception", "exc_message"),
    [
        (
            "/invalid_account_id/album/album_id1/photo_id1",
            Unresolvable,
            "Config entry not found for account: invalid_account_id",
        ),
        (
            "/test_account_id/invalid_view/album_id1/photo_id1",
            Unresolvable,
            "Invalid album view type",
        ),
        (
            "/test_account_id/album/invalid_album_id/photo_id1",
            Unresolvable,
            "Album not found",
        ),
        (
            "/test_account_id/shared/invalid_album_id/photo_id1",
            Unresolvable,
            "Album not found",
        ),
        (
            "/test_account_id/shared/stream_id2/shared_id3",
            Unresolvable,
            "Unsupported media type",
        ),
        (
            "",
            Unresolvable,
            "Incomplete media source identifier",
        ),
    ],
    ids=[
        "invalid_account_id",
        "invalid_view",
        "invalid_album_id_in_album_view",
        "invalid_album_id_in_shared_view",
        "unknown_photo_type_in_shared_stream",
        "unknown_account",
    ],
)
@pytest.mark.usefixtures("icloud_client")
async def test_resolve_media_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    media_content_id: str,
    exception: type[Exception],
    exc_message: str,
) -> None:
    """Test resolving media with exceptions."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(exception, match=exc_message):
        await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}{media_content_id}", None)


@pytest.mark.parametrize(
    ("media_content_id", "service", "has_value", "exception", "exc_message"),
    [
        (
            "/test_account_id/album/album_id1/photo_id1",
            "api",
            False,
            Unresolvable,
            "Account not initialized: test_account_id",
        ),
        (
            "/test_account_id/album/album_id1/photo_id1",
            "api.photos",
            False,
            Exception,
            "Account not initialized: test_account_id",
        ),
        (
            "/test_account_id/shared/album_id1/photo_id1",
            "api",
            False,
            Unresolvable,
            "Account not initialized: test_account_id",
        ),
        (
            "/test_account_id/shared/album_id1/photo_id1",
            "api.photos",
            False,
            Exception,
            "Account not initialized: test_account_id",
        ),
        (
            "/test_account_id/album/album_id1/photo_id1",
            "api.photos.albums",
            True,
            Exception,
            "Photo not found",
        ),
        (
            "/test_account_id/shared/album_id1/photo_id1",
            "api.photos.shared_streams",
            True,
            Exception,
            "Photo not found",
        ),
        (
            "/test_account_id/shared/stream_id1",
            "api.photos.shared_streams.get",
            None,
            Exception,
            "Incomplete media source identifier",
        ),
        (
            "/test_account_id/album/stream_id1",
            "api.photos.albums.get",
            None,
            Exception,
            "Incomplete media source identifier",
        ),
    ],
    ids=[
        "api_not_available_for_album_view",
        "photos_not_available_for_album_view",
        "api_not_available_for_shared_view",
        "photos_not_available_for_shared_view",
        "albums_not_available_for_album_view",
        "shared_streams_not_available_for_shared_view",
        "stream_not_available_for_shared_stream",
        "album_not_available_for_album",
    ],
)
async def test_resolve_media_service_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    icloud_client: AsyncMock,
    media_content_id: str,
    service: str,
    has_value: bool,
    exception: type[Exception],
    exc_message: str,
) -> None:
    """Test resolving media with serviceexceptions."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    parent = icloud_client
    properties = service.split(".")

    while len(properties) > 1:
        prop = properties.pop(0)
        p_mock = PropertyMock()
        setattr(parent, prop, p_mock)
        parent = p_mock
    setattr(
        parent,
        properties[0],
        None if not has_value else PropertyMock(side_effect=exception()),
    )

    with pytest.raises(exception, match=exc_message):
        await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}{media_content_id}", None)


@pytest.mark.parametrize(
    ("album_type", "aid", "exc_message"),
    [
        ("album", "album_id1", "Photo not found"),
        ("album", "album_id13", "Album not found"),
        ("shared", "stream_id1", "Photo not found"),
        ("shared", "stream_id3", "Album not found"),
        ("invalid_type", "stream_id2", "Invalid album view type"),
    ],
    ids=[
        "photo_not_found_in_album",
        "album_not_found_in_album_view",
        "photo_not_found_in_shared_view",
        "album_not_found_in_shared_view",
        "invalid_view_type",
    ],
)
@pytest.mark.usefixtures("icloud_client")
async def test_resolve_media_not_found_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    album_type: str,
    aid: str,
    exc_message: str,
) -> None:
    """Test resolving media with media not found exceptions."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(Unresolvable, match=exc_message):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/test_account_id/{album_type}/{aid}/unknown_photo_id",
            None,
        )


@pytest.mark.usefixtures("icloud_client")
async def test_resolve_media_not_configured(
    hass: HomeAssistant,
) -> None:
    """Test resolving media with no account configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_account_id",
        title="Test iCloud Account",
        data={
            "username": "test_user",
            "password": "test_pass",
            "with_family": False,
            "max_interval": 0,
            "gps_accuracy_threshold": 0,
        },
        disabled_by=ConfigEntryDisabler.USER,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(BrowseError, match="Config entry not loaded"):
        await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}", None)


@pytest.mark.usefixtures("icloud_client")
async def test_resolve_media_no_cache(
    hass: HomeAssistant,
) -> None:
    """Test resolving media with no photo cache configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_account_id",
        title="Test iCloud Account",
        data={
            "username": "test_user",
            "password": "test_pass",
            "with_family": False,
            "max_interval": 0,
            "gps_accuracy_threshold": 0,
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    config_entry.runtime_data.photo_cache = None

    with pytest.raises(Unresolvable, match="Config entry not loaded"):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/test_account_id/album/album_id1/photo_id1",
            None,
        )


@pytest.mark.usefixtures("icloud_client")
async def test_media_source_view_requires_auth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test media source view returns 401 when no auth provided."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    image_id = b64encode(b"test_account_id/album/album_id1/photo_id1").decode()
    client = await hass_client_no_auth()
    resp = await client.get(f"/api/icloud/media_source/serve/original/{image_id}")

    assert resp.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.usefixtures("icloud_client")
async def test_media_source_view_bad_identifier_returns_400(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test media source view returns 400 when identifier is bad."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()
    resp = await client.get("/api/icloud/media_source/serve/original/not-base64")

    assert resp.status == HTTPStatus.BAD_REQUEST


@pytest.mark.usefixtures("icloud_client")
async def test_media_source_view_missing_version_returns_404(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test media source view returns 404 when photo version is missing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    image_id = b64encode(b"test_account_id/album/album_id1/photo_id1").decode()
    client = await hass_client()
    resp = await client.get(f"/api/icloud/media_source/serve/thumb/{image_id}")

    assert resp.status == HTTPStatus.NOT_FOUND


@pytest.mark.usefixtures("icloud_client")
async def test_media_source_view_missing_photo_returns_404(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test media source view returns 404 when photo is missing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    image_id = b64encode(b"test_account_id/album/album_id1/photo_id4").decode()
    client = await hass_client()
    resp = await client.get(f"/api/icloud/media_source/serve/thumb/{image_id}")

    assert resp.status == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("media_content_id", "expected_filename"),
    [
        ("test_account_id/album/album_id1/photo_id1", "My Photo 1.JPG"),
        ("test_account_id/album/album_id1/photo_id2", "My Photo 2.heic"),
        ("test_account_id/album/album_id1/photo_id3", "My Photo 3.png"),
    ],
)
@pytest.mark.usefixtures("icloud_client")
async def test_media_source_view_streams_content_and_headers(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    media_content_id: str,
    expected_filename: str,
) -> None:
    """Test media source view streams content and headers correctly."""

    # Mock upstream iCloud response stream
    class _Content:
        async def iter_chunked(self, _size: int):
            yield b"abc"
            yield b"def"

    upstream_resp = AsyncMock()
    upstream_resp.status = HTTPStatus.OK
    upstream_resp.reason = "OK"
    upstream_resp.headers = {
        hdrs.CONTENT_TYPE: "image/jpeg",
        hdrs.LAST_MODIFIED: "Mon, 01 Jan 2024 00:00:00 GMT",
        hdrs.CONTENT_LENGTH: "6",
    }
    upstream_resp.content = _Content()
    upstream_resp.release.return_value = None

    mock_session = AsyncMock()
    mock_session.get.return_value = upstream_resp

    mock_photo = SimpleNamespace(
        filename=expected_filename,
        versions={"original": {"url": "https://icloud.test/original"}},
    )

    with (
        patch(
            "homeassistant.components.icloud.media_source.async_get_clientsession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.icloud.media_source._get_photo_asset",
            return_value=mock_photo,
        ),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED

    image_id = b64encode(media_content_id.encode()).decode()
    client = await hass_client()
    resp = await client.get(f"/api/icloud/media_source/serve/original/{image_id}")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b"abcdef"
    assert resp.headers[hdrs.CONTENT_TYPE] == "image/jpeg"
    assert (
        resp.headers[hdrs.CONTENT_DISPOSITION]
        == f'attachment;filename="{urllib.parse.quote(expected_filename.encode())}"'
    )


@pytest.mark.usefixtures("icloud_client")
async def test_media_source_view_streams_timeout(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test media source view handles timeout during streaming."""

    # Mock upstream iCloud response stream
    class _Content:
        async def iter_chunked(self, _size: int):
            yield b"abc"
            raise TimeoutError

    upstream_resp = AsyncMock()
    upstream_resp.status = HTTPStatus.OK
    upstream_resp.reason = "OK"
    upstream_resp.headers = {
        hdrs.CONTENT_TYPE: "image/jpeg",
        hdrs.LAST_MODIFIED: "Mon, 01 Jan 2024 00:00:00 GMT",
        hdrs.CONTENT_LENGTH: "6",
    }
    upstream_resp.content = _Content()
    upstream_resp.release.return_value = None

    mock_session = AsyncMock()
    mock_session.get.return_value = upstream_resp

    with (
        patch(
            "homeassistant.components.icloud.media_source.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED

    image_id = b64encode(b"test_account_id/album/album_id1/photo_id1").decode()
    client = await hass_client()

    resp = await client.get(f"/api/icloud/media_source/serve/original/{image_id}")

    assert resp.status == HTTPStatus.OK
    await resp.read()
    assert resp.headers[hdrs.CONTENT_TYPE] == "image/jpeg"
    assert (
        resp.headers[hdrs.CONTENT_DISPOSITION]
        == 'attachment;filename="My%20Photo%201.JPG"'
    )


@pytest.mark.usefixtures("icloud_client")
async def test_media_source_view_streams_content_and_headers_cache_tests(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test media source view streams content and headers correctly and that cache works."""
    expected_filename = "My Photo 1.JPG"
    media_content_id1 = "test_account_id/album/album_id1/photo_id1"
    media_content_id2 = "test_account_id/album/album_id1/photo_id2"

    # Mock upstream iCloud response stream
    class _Content:
        def __init__(self, max_size) -> None:
            self.max_size = max_size

        async def iter_chunked(self, _size: int):
            data = b"abcdef"
            chunk_size = 3
            if self.max_size and len(data) > self.max_size:
                yield data[: self.max_size]
            else:
                for i in range(0, len(data), chunk_size):
                    yield data[i : i + chunk_size]

    def mock_get(url, *args, **kwargs):
        upstream_resp = AsyncMock()
        upstream_resp.status = HTTPStatus.OK
        upstream_resp.reason = "OK"
        upstream_resp.headers = {
            hdrs.CONTENT_TYPE: "image/jpeg",
            hdrs.LAST_MODIFIED: "Mon, 01 Jan 2024 00:00:00 GMT",
            hdrs.CONTENT_LENGTH: "6",
        }
        if size := kwargs.get("headers", {}).get(hdrs.RANGE):
            # to verify that headers are passed correctly
            upstream_resp.headers[hdrs.CONTENT_RANGE] = f"bytes {size.split('=')[1]}/6"
            upstream_resp.headers[hdrs.CONTENT_LENGTH] = size.split("/")[0].split("-")[
                1
            ]
            upstream_resp.status = HTTPStatus.PARTIAL_CONTENT
            upstream_resp.reason = "Partial Content"
        upstream_resp.content = _Content(
            int(upstream_resp.headers[hdrs.CONTENT_LENGTH])
        )
        upstream_resp.release.return_value = None
        return upstream_resp

    mock_session = AsyncMock()
    mock_session.get.side_effect = mock_get

    mock_photo = SimpleNamespace(
        filename=expected_filename,
        versions={"original": {"url": "https://icloud.test/original"}},
    )

    with (
        patch(
            "homeassistant.components.icloud.media_source.async_get_clientsession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.icloud.media_source._get_photo_asset",
            return_value=mock_photo,
        ),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED
        config_entry.runtime_data.photo_cache = PhotoCache(
            max_size=1  # set cache size to 1 to test eviction of first item
        )

    image_id1 = b64encode(media_content_id1.encode()).decode()
    image_id2 = b64encode(media_content_id2.encode()).decode()
    client = await hass_client()
    resp = await client.get(
        f"/api/icloud/media_source/serve/original/{image_id1}",
    )

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b"abcdef"
    assert resp.headers[hdrs.CONTENT_TYPE] == "image/jpeg"
    assert (
        resp.headers[hdrs.CONTENT_DISPOSITION]
        == f'attachment;filename="{urllib.parse.quote(expected_filename.encode())}"'
    )

    # get the same item from the cache to verify that works as well
    resp = await client.get(
        f"/api/icloud/media_source/serve/original/{image_id1}",
        headers={hdrs.RANGE: "bytes=0-2"},
    )
    assert resp.status == HTTPStatus.PARTIAL_CONTENT
    assert await resp.read() == b"ab"

    # get the same item from the cache to verify that works as well
    resp = await client.get(f"/api/icloud/media_source/serve/original/{image_id2}")
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b"abcdef"
