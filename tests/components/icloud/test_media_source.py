"""Tests for media source of the iCloud integration."""

from base64 import b64encode
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientTimeout, hdrs, web
from pyicloud.services.photos import PhotoAlbumFolder
import pytest

from homeassistant.components.icloud.const import DOMAIN
from homeassistant.components.icloud.media_source import (
    MAX_PHOTO_CACHE_SIZE,
    IcloudMediaSource,
    IcloudMediaSourceIdentifier,
    IcloudMediaSourceView,
    PhotoCache,
    _get_icloud_account,
    _get_media_mime_type,
    _get_photo_album,
    _get_photo_asset,
    async_get_media_source,
    async_setup_mediasource,
)
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_account_id",
        title="Test iCloud Account",
    )


async def test_get_media_source(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test getting media source."""
    mock_config_entry.add_to_hass(hass)
    media_source = await async_get_media_source(hass)
    assert isinstance(media_source, IcloudMediaSource)


async def test_setup_mediasource(hass: HomeAssistant) -> None:
    """Test setting up the iCloud media source, registers the API."""
    http_mock = MagicMock()
    hass.http = http_mock
    async_setup_mediasource(hass)

    http_mock.register_view.assert_called_once()
    assert isinstance(http_mock.register_view.call_args[0][0], IcloudMediaSourceView)


async def test_get_icloud_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test getting the iCloud account from the media source identifier."""
    mock_config_entry.add_to_hass(hass)
    mock_account = MagicMock()
    mock_config_entry.runtime_data = mock_account
    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id
    )
    account = _get_icloud_account(hass, identifier)

    assert account == mock_account


async def test_get_icloud_account_no_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test getting the iCloud account from the media source identifier with no entry."""
    mock_config_entry.add_to_hass(hass)
    identifier = IcloudMediaSourceIdentifier(config_entry_id="blah")
    with pytest.raises(Unresolvable):
        _get_icloud_account(hass, identifier)


async def test_get_icloud_account_no_runtime_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test getting the iCloud account from the media source identifier with no runtime data."""
    mock_config_entry.add_to_hass(hass)
    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id
    )
    with pytest.raises(Unresolvable):
        _get_icloud_account(hass, identifier)


async def test_get_icloud_account_no_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test getting the iCloud account from the media source identifier with no account."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = None
    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id
    )
    with pytest.raises(Unresolvable):
        _get_icloud_account(hass, identifier)


async def test_get_photo_album_shared_library(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test getting a photo album from the shared library."""
    mock_account = MagicMock()
    mock_api = MagicMock()
    mock_photos_service = MagicMock()
    mock_account.api = mock_api
    mock_api.photos = mock_photos_service

    mock_shared_library = MagicMock()
    mock_photo_library = MagicMock()

    mock_photos_service.shared_streams = mock_shared_library
    mock_photos_service.albums = mock_photo_library

    album1 = MagicMock()

    mock_shared_library.get.return_value = album1

    # Check shared library
    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=True,
        album_id="shared",
    )
    album = _get_photo_album(mock_account, identifier)

    mock_shared_library.get.assert_called_once()
    mock_photo_library.get.assert_not_called()

    assert album == album1


async def test_get_photo_album_photo_library(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test getting a photo album from the photo library."""
    mock_account = MagicMock()
    mock_api = MagicMock()
    mock_photos_service = MagicMock()
    mock_account.api = mock_api
    mock_api.photos = mock_photos_service

    mock_shared_library = MagicMock()
    mock_photo_library = MagicMock()

    mock_photos_service.shared_streams = mock_shared_library
    mock_photos_service.albums = mock_photo_library

    album1 = MagicMock()
    mock_photo_library.get.return_value = album1

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my photos",
    )
    album = _get_photo_album(mock_account, identifier)

    mock_shared_library.get.assert_not_called()
    mock_photo_library.get.assert_called_once()

    assert album == album1


async def test_get_photo_album_no_api(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test getting a photo album with no API initialized."""
    mock_account = MagicMock()
    mock_account.api = None

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my photos",
    )

    with pytest.raises(Unresolvable, match="account_not_initialized"):
        _get_photo_album(mock_account, identifier)


async def test_get_photo_album_no_album(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test getting a photo album that does not exist."""
    mock_account = MagicMock()
    mock_api = MagicMock()
    mock_photos_service = MagicMock()
    mock_account.api = mock_api
    mock_api.photos = mock_photos_service

    mock_photo_library = MagicMock()
    mock_photos_service.albums = mock_photo_library

    mock_photo_library.get.return_value = None

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my photos",
    )

    with pytest.raises(Unresolvable, match="album_not_found"):
        _get_photo_album(mock_account, identifier)


@patch("homeassistant.components.icloud.media_source._get_icloud_account")
@patch("homeassistant.components.icloud.media_source._get_photo_album")
async def test_get_photo_asset(
    mock_get_photo_album,
    mock_get_icloud_account,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test getting a photo asset."""
    mock_photo = MagicMock(id="1111")

    mock_photos = [
        MagicMock(id="123"),
        MagicMock(id="hello"),
        mock_photo,
        MagicMock(id="5464"),
    ]

    mock_get_photo_album.return_value.photos.__iter__.return_value = iter(mock_photos)

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my photos",
        photo_id="1111",
    )
    photo = _get_photo_asset(hass, identifier)

    assert photo == mock_photo
    mock_get_icloud_account.assert_called_with(hass, identifier)
    mock_get_photo_album.assert_called_with(
        mock_get_icloud_account.return_value, identifier
    )


@patch("homeassistant.components.icloud.media_source._get_icloud_account")
async def test_get_photo_asset_invalid_identifier(
    mock_get_icloud_account, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test getting a photo asset with an invalid identifier."""
    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
    )
    with pytest.raises(Unresolvable, match="incomplete_media_source_identifier"):
        _get_photo_asset(hass, identifier)
    mock_get_icloud_account.assert_called_with(hass, identifier)


@patch("homeassistant.components.icloud.media_source._get_icloud_account")
@patch("homeassistant.components.icloud.media_source._get_photo_album")
async def test_get_photo_asset_photo_in_cache(
    mock_get_photo_album,
    mock_get_icloud_account,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test getting a photo asset that is already in the cache."""
    mock_photo = MagicMock(id="1111")
    PhotoCache.instance().set("1111", mock_photo)
    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my photos",
        photo_id="1111",
    )
    photo = _get_photo_asset(hass, identifier)

    assert photo == mock_photo
    mock_get_icloud_account.assert_called_with(hass, identifier)
    mock_get_photo_album.assert_not_called()


@patch("homeassistant.components.icloud.media_source._get_icloud_account")
@patch("homeassistant.components.icloud.media_source._get_photo_album")
async def test_get_photo_asset_photo_not_found(
    mock_get_photo_album,
    mock_get_icloud_account,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test getting a photo asset that is not found in the album."""
    mock_photo = MagicMock(id="1111")

    mock_photos = [
        MagicMock(id="123"),
        MagicMock(id="hello"),
        mock_photo,
        MagicMock(id="5464"),
    ]

    mock_get_photo_album.return_value.photos.__iter__.return_value = iter(mock_photos)

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my photos",
        photo_id="9999",
    )

    with pytest.raises(Unresolvable, match="photo_not_found"):
        _get_photo_asset(hass, identifier)


@pytest.mark.parametrize(
    ("mock_photo", "expected_mime_type", "raises_exception", "exc_message"),
    [
        (MagicMock(item_type="image", filename="abc.jpg"), "image/jpeg", False, None),
        (MagicMock(item_type="image", filename="abc.heic"), "image/heic", False, None),
        (MagicMock(item_type="image", filename="abc.png"), "image/png", False, None),
        (MagicMock(item_type="image", filename="abc.jpeg"), "image/jpeg", False, None),
        (MagicMock(item_type="image", filename="abc.PNG"), "image/png", False, None),
        (MagicMock(item_type="movie", filename="abc.mp4"), "video/mp4", False, None),
        (MagicMock(item_type="movie", filename="abc.avi"), "video/mp4", False, None),
        (
            MagicMock(item_type="unknown", filename="abc.avi"),
            None,
            True,
            "unsupported_media_type",
        ),
        (None, None, True, "photo_not_found"),
    ],
)
@patch("homeassistant.components.icloud.media_source._get_photo_asset")
async def test_get_media_mime_type(
    mock_get_photo_asset,
    hass: HomeAssistant,
    mock_photo,
    expected_mime_type,
    raises_exception,
    exc_message,
) -> None:
    """Test getting the media mime type."""

    mock_get_photo_asset.return_value = mock_photo
    identifier = IcloudMediaSourceIdentifier(
        config_entry_id="test_account_id",
        photo_id="1111",
    )
    if raises_exception:
        with pytest.raises(Unresolvable, match=exc_message):
            await _get_media_mime_type(hass, identifier)
    else:
        mime_type = await _get_media_mime_type(hass, identifier)
        assert mime_type == expected_mime_type


def test_photo_cache_instance() -> None:
    """Test the PhotoCache singleton instance."""
    cache1 = PhotoCache.instance()
    cache2 = PhotoCache.instance()
    assert cache1 is cache2


def test_photo_cache_set_get() -> None:
    """Test setting and getting items in the PhotoCache."""
    cache = PhotoCache.instance()
    photo_id = "test_photo_id"
    photo_obj = MagicMock()

    cache.set(photo_id, photo_obj)
    retrieved_photo = cache.get(photo_id)

    assert retrieved_photo == photo_obj


def test_photo_cache_get_nonexistent() -> None:
    """Test getting a nonexistent item from the PhotoCache."""
    cache = PhotoCache.instance()
    retrieved_photo = cache.get("nonexistent_photo_id")
    assert retrieved_photo is None


def test_photo_cache_set_overwrite() -> None:
    """Test overwriting an existing item in the PhotoCache."""
    cache = PhotoCache.instance()
    photo_id = "test_photo_id"
    photo_obj1 = MagicMock()
    photo_obj2 = MagicMock()

    cache.set(photo_id, photo_obj1)
    cache.set(photo_id, photo_obj2)
    retrieved_photo = cache.get(photo_id)

    assert retrieved_photo == photo_obj2


def test_photo_cache_set_clears_last_item_if_full() -> None:
    """Test that setting a new item clears the last item if the cache is full."""
    cache = PhotoCache.instance()
    # Fill the cache to its max size
    for i in range(MAX_PHOTO_CACHE_SIZE):
        cache.set(f"photo_id_{i}", MagicMock())

    # Add one more item to trigger the clearing of the last item
    new_photo_id = "new_photo_id"
    new_photo_obj = MagicMock()
    cache.set(new_photo_id, new_photo_obj)

    # The first item should have been removed
    assert cache.get("photo_id_0") is None
    # The new item should be present
    assert cache.get(new_photo_id) == new_photo_obj


def test_photo_cache_size_limit() -> None:
    """Test that the PhotoCache does not exceed its maximum size."""
    cache = PhotoCache.instance()
    # Clear the cache first
    cache._cache.clear()

    # Add items up to the max size
    for i in range(MAX_PHOTO_CACHE_SIZE):
        cache.set(f"photo_id_{i}", MagicMock())

    assert len(cache._cache) == MAX_PHOTO_CACHE_SIZE

    # Add one more item to exceed the max size
    cache.set("exceeding_photo_id", MagicMock())

    # The cache size should still be at max size
    assert len(cache._cache) == MAX_PHOTO_CACHE_SIZE


def test_photo_cache_get_moved_to_top() -> None:
    """Test that getting an item moves it to the top of the cache."""
    cache = PhotoCache.instance()
    # Clear the cache first
    cache._cache.clear()

    photo_id1 = "photo_id_1"
    photo_id2 = "photo_id_2"
    photo_obj1 = MagicMock()
    photo_obj2 = MagicMock()

    cache.set(photo_id1, photo_obj1)
    cache.set(photo_id2, photo_obj2)

    # Access the first photo to move it to the top
    cache.get(photo_id1)

    # Add more items to exceed the max size
    for i in range(MAX_PHOTO_CACHE_SIZE - 1):
        cache.set(f"photo_id_{i + 3}", MagicMock())

    # The second photo should have been removed since the first was accessed
    assert cache.get(photo_id2) is None
    # The first photo should still be present
    assert cache.get(photo_id1) == photo_obj1


def test_icloud_media_source_identifier_str_missing_fields() -> None:
    """Test the string conversion and parsing of IcloudMediaSourceIdentifier with missing fields."""
    identifier = IcloudMediaSourceIdentifier(
        config_entry_id="test_entry",
    )
    identifier_str = str(identifier)
    parsed_identifier = IcloudMediaSourceIdentifier.from_identifier(identifier_str)

    assert identifier == parsed_identifier


def test_icloud_media_source_identifier_to_str() -> None:
    """Test the string representation of IcloudMediaSourceIdentifier."""
    identifier = IcloudMediaSourceIdentifier(
        config_entry_id="entry1",
        shared_album=False,
        album_id="albumA",
        photo_id="photoX",
    )
    expected_str = "entry1/album/albumA/photoX"
    assert str(identifier) == expected_str

    parsed_identifier = IcloudMediaSourceIdentifier.from_identifier(expected_str)
    assert identifier == parsed_identifier

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id="entry1",
        shared_album=False,
        album_id="albumA",
    )
    expected_str = "entry1/album/albumA"
    assert str(identifier) == expected_str

    parsed_identifier = IcloudMediaSourceIdentifier.from_identifier(expected_str)
    assert identifier == parsed_identifier

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id="entry1",
        shared_album=False,
    )
    expected_str = "entry1/album"
    assert str(identifier) == expected_str

    parsed_identifier = IcloudMediaSourceIdentifier.from_identifier(expected_str)
    assert identifier == parsed_identifier

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id="entry1",
    )
    expected_str = "entry1"
    assert str(identifier) == expected_str

    parsed_identifier = IcloudMediaSourceIdentifier.from_identifier(expected_str)
    assert identifier == parsed_identifier


@patch("homeassistant.components.icloud.media_source._get_media_mime_type")
async def test_icloud_media_source_resolve_media(
    mock_get_media_mime_type, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test resolving media source items."""
    mock_config_entry.add_to_hass(hass)
    mock_get_media_mime_type.return_value = "my_mime_type"

    media_source = IcloudMediaSource(hass)

    item = MediaSourceItem(
        hass,
        domain=DOMAIN,
        target_media_player="browser",
        identifier="invalid_identifier",
    )

    media_item = await media_source.async_resolve_media(item)

    assert isinstance(media_item, PlayMedia)
    assert media_item.mime_type == "my_mime_type"
    assert media_item.url.startswith(
        f"/api/icloud/media_source/serve/original/{b64encode(b'invalid_identifier').decode('utf-8')}"
    )


@pytest.mark.parametrize(
    ("identifier", "expected_title"),
    [
        (None, "iCloud Media"),
        (IcloudMediaSourceIdentifier(config_entry_id=None), "iCloud Media"),
        (
            IcloudMediaSourceIdentifier(
                config_entry_id="test_account_id",
            ),
            "iCloud Media / Test iCloud Account",
        ),
        (
            IcloudMediaSourceIdentifier(
                config_entry_id="test_account_id",
                shared_album=True,
            ),
            "iCloud Media / Test iCloud Account / Shared Streams",
        ),
        (
            IcloudMediaSourceIdentifier(
                config_entry_id="test_account_id",
                shared_album=False,
            ),
            "iCloud Media / Test iCloud Account / Albums",
        ),
        (
            IcloudMediaSourceIdentifier(
                config_entry_id="test_account_id",
                shared_album=False,
                album_id="my_album",
            ),
            "iCloud Media / Test iCloud Account / Albums / My Album",
        ),
        (
            IcloudMediaSourceIdentifier(
                config_entry_id="test_account_id",
                shared_album=True,
                album_id="my_shared_album",
            ),
            "iCloud Media / Test iCloud Account / Shared Streams / My Album",
        ),
    ],
)
@patch("homeassistant.components.icloud.media_source._get_icloud_account")
@patch("homeassistant.components.icloud.media_source._get_photo_album")
@patch(
    "homeassistant.components.icloud.media_source.IcloudMediaSource._get_config_entries"
)
async def test_build_title_for_identifier(
    mock_get_config_entries,
    mock_get_photo_album,
    mock_get_icloud_account,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    identifier: IcloudMediaSourceIdentifier | None,
    expected_title: str,
) -> None:
    """Test building title for media source identifier."""
    mock_config_entry.add_to_hass(hass)
    media_source = IcloudMediaSource(hass)
    mock_get_config_entries.return_value = [mock_config_entry]
    mock_get_photo_album.return_value.title = "My Album"

    assert media_source._build_title_for_identifier(identifier) == expected_title

    if identifier is not None and identifier.config_entry_id is not None:
        mock_get_icloud_account.assert_called_with(hass, identifier)

    if identifier is not None and identifier.album_id is not None:
        mock_get_photo_album.assert_called_with(
            mock_get_icloud_account.return_value, identifier
        )


@patch("homeassistant.components.icloud.media_source._get_icloud_account")
@patch("homeassistant.components.icloud.media_source._get_photo_album")
@patch(
    "homeassistant.components.icloud.media_source.IcloudMediaSource._get_config_entries"
)
async def test_build_title_for_identifier_invalid(
    mock_get_config_entries,
    mock_get_photo_album,
    mock_get_icloud_account,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test building title for invalid media source identifier."""
    mock_config_entry.add_to_hass(hass)
    media_source = IcloudMediaSource(hass)
    mock_get_config_entries.return_value = [mock_config_entry]
    mock_get_photo_album.return_value.title = "My Album"

    with pytest.raises(
        Unresolvable,
        match="config_entry_not_found",
    ):
        media_source._build_title_for_identifier(
            IcloudMediaSourceIdentifier(config_entry_id="invalid_entry_id")
        )


async def test_icloud_media_source_resolve_media_invalid_domain(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test resolving media source items with invalid domain."""
    mock_config_entry.add_to_hass(hass)

    media_source = IcloudMediaSource(hass)

    item = MediaSourceItem(
        hass,
        domain="invalid_domain",
        target_media_player="browser",
        identifier="some_identifier",
    )

    with pytest.raises(Unresolvable, match="invalid_media_source"):
        await media_source.async_resolve_media(item)


async def test_icloud_media_source_browse_media_not_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test browsing media source items."""
    mock_config_entry.add_to_hass(hass)
    media_source = IcloudMediaSource(hass)
    item = MediaSourceItem(
        hass,
        domain=DOMAIN,
        target_media_player="browser",
        identifier="some_identifier",
    )
    with pytest.raises(BrowseError, match="config_entry_not_loaded"):
        await media_source.async_browse_media(item)


@patch("homeassistant.components.icloud.async_setup_entry", return_value=True)
async def test_icloud_media_source_browse_media(
    mock_setup_entry,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browsing media source items."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    media_source = IcloudMediaSource(hass)

    item = MediaSourceItem(hass, DOMAIN, None, None)

    media_item: BrowseMediaSource = await media_source.async_browse_media(item)

    assert media_item is not None

    assert len(media_item.children) == 1  # One iCloud account


@patch("homeassistant.components.icloud.async_setup_entry", return_value=True)
@patch("homeassistant.components.icloud.media_source._get_icloud_account")
@patch(
    "homeassistant.components.icloud.media_source.IcloudMediaSource._async_build_album_types"
)
async def test_icloud_media_source_browse_media_account(
    mock_build_album_types,
    mock_get_icloud_account,
    mock_setup_entry,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browsing media source items."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    mock_get_icloud_account.return_value.config_entry.title = mock_config_entry.title

    media_source = IcloudMediaSource(hass)
    item = MediaSourceItem(
        hass,
        domain=DOMAIN,
        target_media_player="browser",
        identifier=f"{mock_config_entry.unique_id}",
    )

    media_item: BrowseMediaSource = await media_source.async_browse_media(item)

    assert media_item is not None

    mock_build_album_types.assert_called_once()


@patch("homeassistant.components.icloud.async_setup_entry", return_value=True)
@patch("homeassistant.components.icloud.media_source._get_icloud_account")
@patch(
    "homeassistant.components.icloud.media_source.IcloudMediaSource._async_build_albums"
)
async def test_icloud_media_source_browse_albums(
    mock_build_albums,
    mock_get_icloud_account,
    mock_setup_entry,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browsing media source items."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    mock_get_icloud_account.return_value.config_entry.title = mock_config_entry.title

    media_source = IcloudMediaSource(hass)
    item = MediaSourceItem(
        hass,
        domain=DOMAIN,
        target_media_player="browser",
        identifier=f"{mock_config_entry.unique_id}/{False}",
    )

    media_item: BrowseMediaSource = await media_source.async_browse_media(item)

    assert media_item is not None

    mock_build_albums.assert_called_once()


@patch("homeassistant.components.icloud.async_setup_entry", return_value=True)
@patch("homeassistant.components.icloud.media_source._get_icloud_account")
@patch(
    "homeassistant.components.icloud.media_source.IcloudMediaSource._async_build_photos"
)
async def test_icloud_media_source_browse_photos(
    mock_build_photos,
    mock_get_icloud_account,
    mock_setup_entry,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browsing media source items."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    mock_get_icloud_account.return_value.config_entry.title = mock_config_entry.title

    media_source = IcloudMediaSource(hass)
    item = MediaSourceItem(
        hass,
        domain=DOMAIN,
        target_media_player="browser",
        identifier=f"{mock_config_entry.unique_id}/{False}/my_album",
    )

    media_item: BrowseMediaSource = await media_source.async_browse_media(item)

    assert media_item is not None

    mock_build_photos.assert_called_once()


@patch("homeassistant.components.icloud.async_setup_entry", return_value=True)
@patch("homeassistant.components.icloud.media_source._get_icloud_account")
async def test_icloud_media_source_browse_invalid(
    mock_get_icloud_account,
    mock_setup_entry,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browsing media source items."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    mock_get_icloud_account.return_value.config_entry.title = mock_config_entry.title

    media_source = IcloudMediaSource(hass)
    item = MediaSourceItem(
        hass,
        domain=DOMAIN,
        target_media_player="browser",
        identifier=f"{mock_config_entry.unique_id}/{False}/my_album/aaaa",
    )

    with pytest.raises(
        BrowseError,
        match="Unknown media item",
    ):
        await media_source.async_browse_media(item)


@patch(
    "homeassistant.components.icloud.media_source.IcloudMediaSource._get_config_entries"
)
async def test_build_icloud_accounts(
    mock_get_config_entries, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test building iCloud accounts list."""
    mock_config_entry.add_to_hass(hass)
    media_source = IcloudMediaSource(
        hass,
    )

    mock_get_config_entries.return_value = [
        MagicMock(unique_id="123", title="user@icloud.com"),
        MagicMock(unique_id="456", title="another_user@icloud.com"),
    ]

    accounts = await media_source._async_build_icloud_accounts()

    assert len(accounts.children) == 2
    assert accounts.children[0].title == "user@icloud.com"
    assert accounts.children[1].title == "another_user@icloud.com"


@patch("homeassistant.components.icloud.media_source._get_icloud_account")
async def test_build_icloud_album_types(
    mock_get_icloud_account, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test building iCloud album types list."""
    mock_config_entry.add_to_hass(hass)

    media_source = IcloudMediaSource(
        hass,
    )

    mock_get_icloud_account.return_value.config_entry.title = "user@icloud.com"

    ident = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
    )
    albums_types = await media_source._async_build_album_types(ident)

    assert len(albums_types.children) == 2
    assert albums_types.children[0].title == "Albums"
    assert albums_types.children[1].title == "Shared Streams"


@patch("homeassistant.components.icloud.media_source._get_icloud_account")
@patch("homeassistant.components.icloud.media_source._get_photo_album")
@patch("homeassistant.components.icloud.media_source.IcloudMediaSource._browse_albums")
async def test_build_icloud_albums(
    mock_browse_albums,
    mock_get_photo_album,
    mock_get_icloud_account,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test building iCloud albums list."""
    mock_config_entry.add_to_hass(hass)

    media_source = IcloudMediaSource(
        hass,
    )

    mock_get_icloud_account.return_value.config_entry.title = "user@icloud.com"
    mock_browse_albums.return_value = [
        MagicMock(title="Albums 1"),
        MagicMock(title="Albums 2"),
        MagicMock(title="Albums 3"),
        MagicMock(title="Albums 4"),
        MagicMock(title="Albums 5"),
    ]

    mock_get_photo_album.side_effect = mock_browse_albums.return_value

    ident = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
    )
    account = MagicMock()
    albums = await media_source._async_build_albums(ident, account)

    assert len(albums.children) == 5
    assert albums.children == mock_browse_albums.return_value
    mock_browse_albums.assert_called_with(account, ident)


@patch("homeassistant.components.icloud.media_source._get_icloud_account")
@patch("homeassistant.components.icloud.media_source._get_photo_album")
@patch("homeassistant.components.icloud.media_source.IcloudMediaSource._get_photo_list")
async def test_build_photos(
    mock_get_photo_list,
    mock_get_photo_album,
    mock_get_icloud_account,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test building iCloud photos list."""
    mock_config_entry.add_to_hass(hass)

    media_source = IcloudMediaSource(
        hass,
    )

    mock_get_icloud_account.return_value.config_entry.title = "user@icloud.com"
    mock_get_photo_list.return_value = [
        MagicMock(title="Photo 1"),
        MagicMock(title="Photo 2"),
        MagicMock(title="Photo 3"),
        MagicMock(title="Photo 4"),
        MagicMock(title="Photo 5"),
    ]

    mock_get_photo_album.side_effect = [
        MagicMock(title="Albums 1"),
        MagicMock(title="Albums 2"),
        MagicMock(title="Albums 3"),
        MagicMock(title="Albums 4"),
        MagicMock(title="Albums 5"),
    ]

    ident = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
    )
    account = MagicMock()
    albums = await media_source._async_build_photos(ident, account)

    assert len(albums.children) == 5
    assert albums.children == mock_get_photo_list.return_value
    mock_get_photo_list.assert_called_with(ident, account)


async def test_browse_albums(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test browsing albums."""
    mock_account = MagicMock()

    mock_album1 = MagicMock(title="Album 1", id="1")
    mock_album2 = MagicMock(title="Album 2", id="2")

    mock_album_list = [
        mock_album1,
        MagicMock(
            spec=PhotoAlbumFolder, title="Non-album item", id="3"
        ),  # Non-album item to be filtered out
        mock_album2,
    ]

    media_source = IcloudMediaSource(hass)

    ident = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
    )

    mock_account.api.photos.albums.__iter__.return_value = iter(mock_album_list)

    albums = media_source._browse_albums(mock_account, ident)

    assert len(albums) == 2
    assert albums[0].title == "Album 1"
    assert albums[1].title == "Album 2"
    mock_account.api.photos.albums.__iter__.assert_called_once()

    ident = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=True,
    )

    mock_account.api.photos.shared_streams.__iter__.return_value = iter(mock_album_list)

    albums = media_source._browse_albums(mock_account, ident)

    assert len(albums) == 2
    assert albums[0].title == "Album 1"
    assert albums[1].title == "Album 2"
    mock_account.api.photos.shared_streams.__iter__.assert_called_once()


async def test_browse_albums_no_albums(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test browsing albums when there are no albums."""
    mock_account = MagicMock()
    mock_api = MagicMock()
    mock_account.api = mock_api

    media_source = IcloudMediaSource(hass)

    ident = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
    )

    mock_api.photos.albums.__iter__.return_value = iter([])

    albums = media_source._browse_albums(mock_account, ident)

    assert len(albums) == 0
    mock_api.photos.albums.__iter__.assert_called_once()


async def test_browse_albums_no_api(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test browsing albums with no API initialized."""
    mock_account = MagicMock()
    mock_account.api = None

    media_source = IcloudMediaSource(hass)

    ident = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
    )

    with pytest.raises(BrowseError, match="account_not_initialized"):
        media_source._browse_albums(mock_account, ident)


async def test_browse_albums_no_album_type(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test browsing albums with no album type specified."""
    mock_account = MagicMock()
    mock_api = MagicMock()
    mock_account.api = mock_api

    media_source = IcloudMediaSource(hass)

    ident = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
    )

    with pytest.raises(BrowseError, match="album_type_not_specified"):
        media_source._browse_albums(mock_account, ident)


async def test_get_photo_list(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test getting photo list from an album."""
    mock_account = MagicMock()
    mock_api = MagicMock()
    mock_photos_service = MagicMock()
    mock_account.api = mock_api
    mock_api.photos = mock_photos_service

    mock_album = MagicMock()
    photo1 = MagicMock(
        title="Photo 1", id="1", filename="photo1.jpg", item_type="image"
    )
    photo2 = MagicMock(
        title="Photo 2", id="2", filename="photo2.jpg", item_type="image"
    )
    photo3 = MagicMock(
        title="Photo 3", id="3", filename="photo3.jpg", item_type="image"
    )
    photo4 = MagicMock(
        title="Video 4", id="4", filename="video4.mp4", item_type="movie"
    )

    mock_album.photos.__iter__.return_value = iter([photo1, photo2, photo3, photo4])
    mock_photos_service.albums.get.return_value = mock_album

    media_source = IcloudMediaSource(hass)

    ident = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my_album",
    )

    photos = media_source._get_photo_list(ident, mock_account)

    results = (
        (
            "photo1.jpg",
            1,
            MediaClass.IMAGE,
        ),
        (
            "photo2.jpg",
            2,
            MediaClass.IMAGE,
        ),
        (
            "photo3.jpg",
            3,
            MediaClass.IMAGE,
        ),
        (
            "video4.mp4",
            4,
            MediaClass.VIDEO,
        ),
    )

    assert len(photos) == 4
    for i, photo in enumerate(photos):
        assert photo.title == results[i][0]
        assert photo.identifier == f"test_account_id/album/my_album/{results[i][1]}"
        assert (
            photo.thumbnail
            == f"/api/icloud/media_source/serve/thumb/{b64encode(photo.identifier.encode()).decode('utf-8')}"
        )
        assert photo.media_class == results[i][2]
        assert photo.can_play is True
        assert photo.can_expand is False
    mock_album.photos.__iter__.assert_called_once()


@patch("homeassistant.components.icloud.media_source._get_photo_asset")
async def test_view_get_no_photo_asset(
    mock_photo_asset, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the media source view GET method."""
    media_source_view = IcloudMediaSourceView(hass)

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my_album",
        photo_id="my_photo",
    )

    mock_photo_asset.return_value = None

    with pytest.raises(web.HTTPNotFound):
        await media_source_view.get(
            MagicMock(),
            "thumb",
            b64encode(str(identifier).encode("utf-8")).decode("utf-8"),
        )


@patch("homeassistant.components.icloud.media_source._get_photo_asset")
async def test_view_get_success(
    mock_photo_asset, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the media source view GET method for successful response."""

    async def mock_iter_chunked(chunk_size):
        yield b"chunk1"
        yield b"chunk2"
        yield b"chunk3"

    mock_session = MagicMock()
    mock_session.get = AsyncMock()

    # Mock the iCloud response
    mock_icloud_response = MagicMock()
    mock_icloud_response.status = 200
    mock_icloud_response.reason = "OK"
    mock_icloud_response.headers = {
        hdrs.CONTENT_TYPE: "image/jpeg",
        "Custom-Header": "custom-value",
    }
    mock_icloud_response.content.iter_chunked = mock_iter_chunked
    mock_session.get.return_value = mock_icloud_response

    media_source_view = IcloudMediaSourceView(hass)
    media_source_view.session = mock_session

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my_album",
        photo_id="my_photo",
    )

    photo = MagicMock()
    photo.filename = "test_photo.jpg"
    photo.versions = {
        "thumb": {"url": "http://example.com/thumb.jpg"},
        "original": {"url": "http://example.com/original.jpg"},
    }
    mock_photo_asset.return_value = photo

    mock_request = MagicMock()
    mock_response = MagicMock()

    with patch("aiohttp.web.StreamResponse", return_value=mock_response):
        mock_response.prepare = AsyncMock()
        mock_response.write = AsyncMock()
        mock_response.write_eof = AsyncMock()

        result = await media_source_view.get(
            mock_request,
            "thumb",
            b64encode(str(identifier).encode("utf-8")).decode("utf-8"),
        )

        # Verify the session was called with correct URL and timeout
        mock_session.get.assert_called_once_with(
            "http://example.com/thumb.jpg",
            timeout=ClientTimeout(connect=15, sock_connect=15, sock_read=5, total=None),
        )

        # Verify response preparation
        mock_response.prepare.assert_called_once_with(mock_request)

        # Verify chunks were written
        assert mock_response.write.call_count == 3
        mock_response.write.assert_any_call(b"chunk1")
        mock_response.write.assert_any_call(b"chunk2")
        mock_response.write.assert_any_call(b"chunk3")

        # Verify EOF was written
        mock_response.write_eof.assert_called_once()

        # Verify response was released
        mock_icloud_response.release.assert_called_once()

        # Verify the response is returned
        assert result == mock_response


@patch("homeassistant.components.icloud.media_source._get_photo_asset")
async def test_view_get_with_timeout_error(
    mock_photo_asset, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the media source view GET method with timeout during chunk reading."""
    mock_session = MagicMock()
    mock_session.get = AsyncMock()

    # Mock the iCloud response
    mock_icloud_response = MagicMock()
    mock_icloud_response.status = 200
    mock_icloud_response.reason = "OK"
    mock_icloud_response.headers = {hdrs.CONTENT_TYPE: "image/jpeg"}

    # Mock iter_chunked to raise TimeoutError after first chunk
    async def mock_iter_chunked(chunk_size):
        yield b"chunk1"
        raise TimeoutError("Connection timeout")

    mock_icloud_response.content.iter_chunked = mock_iter_chunked
    mock_session.get.return_value = mock_icloud_response

    media_source_view = IcloudMediaSourceView(hass)
    media_source_view.session = mock_session

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my_album",
        photo_id="my_photo",
    )

    photo = MagicMock()
    photo.filename = "test_photo.jpg"
    photo.versions = {"original": {"url": "http://example.com/original.jpg"}}
    mock_photo_asset.return_value = photo

    mock_request = MagicMock()
    mock_response = MagicMock()

    with (
        patch("aiohttp.web.StreamResponse", return_value=mock_response),
        patch("homeassistant.components.icloud.media_source._LOGGER") as mock_logger,
    ):
        mock_response.prepare = AsyncMock()
        mock_response.write = AsyncMock()
        mock_response.write_eof = AsyncMock()

        await media_source_view.get(
            mock_request,
            "original",
            b64encode(str(identifier).encode("utf-8")).decode("utf-8"),
        )

        # Verify timeout was logged
        mock_logger.debug.assert_called_once_with(
            "Timeout while reading iCloud, writing EOF"
        )

        # Verify only first chunk was written before timeout
        mock_response.write.assert_called_once_with(b"chunk1")

        # Verify response was still finalized
        mock_response.write_eof.assert_called_once()
        mock_icloud_response.release.assert_called_once()


@patch("homeassistant.components.icloud.media_source._get_photo_asset")
async def test_view_get_with_default_content_type(
    mock_photo_asset, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the media source view GET method with default content type."""
    mock_session = MagicMock()
    mock_session.get = AsyncMock()

    # Mock the iCloud response without content type header
    mock_icloud_response = MagicMock()
    mock_icloud_response.status = 200
    mock_icloud_response.reason = "OK"
    mock_icloud_response.headers = {}  # No content type header

    async def mock_iter_chunked(chunk_size):
        yield b"chunk1"

    mock_icloud_response.content.iter_chunked = mock_iter_chunked
    mock_session.get.return_value = mock_icloud_response

    media_source_view = IcloudMediaSourceView(hass)
    media_source_view.session = mock_session

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my_album",
        photo_id="my_photo",
    )

    photo = MagicMock()
    photo.filename = "test_photo.jpg"
    photo.versions = {"thumb": {"url": "http://example.com/thumb.jpg"}}
    mock_photo_asset.return_value = photo

    mock_request = MagicMock()
    mock_response = MagicMock()

    with patch(
        "aiohttp.web.StreamResponse", return_value=mock_response
    ) as mock_stream_response:
        mock_response.prepare = AsyncMock()
        mock_response.write = AsyncMock()
        mock_response.write_eof = AsyncMock()

        await media_source_view.get(
            mock_request,
            "thumb",
            b64encode(str(identifier).encode("utf-8")).decode("utf-8"),
        )

        # Verify StreamResponse was created with correct headers including default content type
        call_args = mock_stream_response.call_args[1]
        assert call_args["headers"][hdrs.CONTENT_TYPE] == "application/octet-stream"
        assert (
            call_args["headers"][hdrs.CONTENT_DISPOSITION]
            == 'attachment;filename="test_photo.jpg"'
        )


@patch("homeassistant.components.icloud.media_source._get_photo_asset")
async def test_view_get_response_headers(
    mock_photo_asset, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that response headers are properly set including cache headers."""
    mock_session = MagicMock()
    mock_session.get = AsyncMock()

    mock_icloud_response = MagicMock()
    mock_icloud_response.status = 404
    mock_icloud_response.reason = "Not Found"
    mock_icloud_response.headers = {
        hdrs.CONTENT_TYPE: "image/png",
        "Original-Header": "original-value",
    }

    async def mock_iter_chunked(chunk_size):
        yield b"chunk1"

    mock_icloud_response.content.iter_chunked = mock_iter_chunked
    mock_session.get.return_value = mock_icloud_response

    media_source_view = IcloudMediaSourceView(hass)
    media_source_view.session = mock_session

    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=True,
        album_id="shared_album",
        photo_id="shared_photo",
    )

    photo = MagicMock()
    photo.filename = "shared_photo.heic"
    photo.versions = {"original": {"url": "http://example.com/shared.heic"}}
    mock_photo_asset.return_value = photo

    mock_request = MagicMock()
    mock_response = MagicMock()

    with (
        patch(
            "aiohttp.web.StreamResponse", return_value=mock_response
        ) as mock_stream_response,
        patch(
            "homeassistant.components.icloud.media_source.CACHE_HEADERS",
            {"Cache-Control": "max-age=3600"},
        ),
    ):
        mock_response.prepare = AsyncMock()
        mock_response.write = AsyncMock()
        mock_response.write_eof = AsyncMock()

        await media_source_view.get(
            mock_request,
            "original",
            b64encode(str(identifier).encode("utf-8")).decode("utf-8"),
        )

        # Verify StreamResponse was created with correct status and headers
        call_args = mock_stream_response.call_args[1]
        assert call_args["status"] == 404
        assert call_args["reason"] == "Not Found"

        headers = call_args["headers"]
        assert headers[hdrs.CONTENT_TYPE] == "image/png"
        assert (
            headers[hdrs.CONTENT_DISPOSITION]
            == 'attachment;filename="shared_photo.heic"'
        )
        assert (
            headers["Cache-Control"] == "max-age=3600"
        )  # Cache headers should be included
        assert (
            "Original-Header" not in headers
        )  # Original headers from iCloud response should not be included


@patch("homeassistant.components.icloud.media_source._get_photo_asset")
async def test_view_get_invalid_identifier(
    mock_photo_asset, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the media source view GET method with invalid base64 identifier."""
    media_source_view = IcloudMediaSourceView(hass)

    # Test with invalid base64
    with pytest.raises(web.HTTPBadRequest):
        await media_source_view.get(
            MagicMock(),
            "thumb",
            "invalid_base64!",
        )


@patch("homeassistant.components.icloud.media_source._get_photo_asset")
async def test_view_get_invalid_version(
    mock_photo_asset, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the media source view GET method with invalid base64 identifier."""
    mock_config_entry.add_to_hass(hass)
    media_source_view = IcloudMediaSourceView(hass)
    identifier = IcloudMediaSourceIdentifier(
        config_entry_id=mock_config_entry.unique_id,
        shared_album=False,
        album_id="my_album",
        photo_id="my_photo",
    )

    ident = b64encode(str(identifier).encode("utf-8")).decode("utf-8")

    photo = MagicMock()
    photo.versions = {"original": {"url": "http://example.com/original.jpg"}}
    mock_photo_asset.return_value = photo

    with pytest.raises(web.HTTPNotFound):
        await media_source_view.get(
            MagicMock(),
            "thumb",
            ident,
        )
