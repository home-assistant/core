"""Tests for media source of the iCloud integration."""

from collections.abc import Generator
from unittest.mock import PropertyMock, patch

from pyicloud.services.photos import AlbumContainer, PhotoAsset
import pytest

from homeassistant.components.icloud.const import DOMAIN
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
from tests.typing import MagicMock


@pytest.fixture(name="icloud_client")
def mock_icloud_client() -> Generator[AsyncMock]:
    """Mock iCloud client."""
    with (
        patch(
            "homeassistant.components.icloud.account.IcloudAccount", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.icloud.IcloudAccount",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.api = MagicMock()

        albums = [
            MagicMock(
                id="album_id1",
                title="All Photos",
                photos=[
                    MagicMock(
                        spec=PhotoAsset,
                        id="photo_id1",
                        filename="My Photo 1.jpg",
                        item_type="image",
                    ),
                    MagicMock(
                        spec=PhotoAsset,
                        id="photo_id2",
                        filename="My Photo 2.jpg",
                        item_type="image",
                    ),
                    MagicMock(
                        spec=PhotoAsset,
                        id="photo_id3",
                        filename="My Photo 3.png",
                        item_type="image",
                    ),
                ],
            ),
            MagicMock(
                id="album_id2",
                title="My Photos",
                photos=[
                    MagicMock(
                        spec=PhotoAsset,
                        id="photo_id2",
                        filename="My Photo 2.jpg",
                        item_type="image",
                    ),
                ],
            ),
        ]

        shared = [
            MagicMock(
                id="stream_id1",
                title="Favorites",
                photos=[
                    MagicMock(
                        spec=PhotoAsset,
                        id="shared_id1",
                        filename="My Photo 1.jpg",
                        item_type="image",
                    ),
                    MagicMock(
                        spec=PhotoAsset,
                        id="shared_id2",
                        filename="My Video 1.mp4",
                        item_type="movie",
                    ),
                ],
            ),
        ]

        client.api.photos.albums = AlbumContainer(albums)
        client.api.photos.shared_streams = AlbumContainer(shared)
        yield client


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
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
            1,
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
            "image/jpeg",
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
        "album_1_photo",
        "album_2_photo",
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
    ("media_content_id", "service", "has_value", "exception"),
    [
        (
            "/invalid_account_id/album/album_id1/photo_id1",
            None,
            None,
            Unresolvable,
        ),
        (
            "/test_account_id/invalid_view/album_id1/photo_id1",
            None,
            None,
            Unresolvable,
        ),
        (
            "/test_account_id/album/invalid_album_id/photo_id1",
            None,
            None,
            Unresolvable,
        ),
        (
            "/test_account_id/shared/invalid_album_id/photo_id1",
            None,
            None,
            Unresolvable,
        ),
        (
            "/test_account_id/album/album_id1/photo_id1",
            "api",
            False,
            Unresolvable,
        ),
        (
            "/test_account_id/album/album_id1/photo_id1",
            "api.photos",
            False,
            Exception,
        ),
        (
            "/test_account_id/shared/album_id1/photo_id1",
            "api",
            False,
            Unresolvable,
        ),
        (
            "/test_account_id/shared/album_id1/photo_id1",
            "api.photos",
            False,
            Exception,
        ),
        (
            "/test_account_id/album/album_id1/photo_id1",
            "api.photos.albums",
            True,
            Exception,
        ),
        (
            "/test_account_id/shared/album_id1/photo_id1",
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
async def test_resolve_media_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    icloud_client: AsyncMock,
    media_content_id: str,
    service: str,
    has_value: bool,
    exception: type[Exception],
) -> None:
    """Test resolving media with exceptions."""
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
        await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}{media_content_id}", None)


@pytest.mark.parametrize(
    ("album_type", "aid", "exc_message"),
    [
        ("album", "album_id1", "Photo not found"),
        ("album", "album_id13", "Album not found"),
        ("shared", "stream_id1", "Photo not found"),
        ("shared", "stream_id2", "Album not found"),
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
