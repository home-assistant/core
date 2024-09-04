"""Test fixtures for Google Photos."""

from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
import time
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from google_photos_library_api.api import GooglePhotosLibraryApi
from google_photos_library_api.model import (
    Album,
    ListAlbumResult,
    ListMediaItemResult,
    MediaItem,
    UserInfoResult,
)
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_photos.const import DOMAIN, OAUTH2_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

USER_IDENTIFIER = "user-identifier-1"
CONFIG_ENTRY_ID = "user-identifier-1"
CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = "some-access-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"
EXPIRES_IN = 3600
USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
PHOTOS_BASE_URL = "https://photoslibrary.googleapis.com"
MEDIA_ITEMS_URL = f"{PHOTOS_BASE_URL}/v1/mediaItems"
ALBUMS_URL = f"{PHOTOS_BASE_URL}/v1/albums"
UPLOADS_URL = f"{PHOTOS_BASE_URL}/v1/uploads"
CREATE_MEDIA_ITEMS_URL = f"{PHOTOS_BASE_URL}/v1/mediaItems:batchCreate"


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + EXPIRES_IN


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set scopes used during the config entry."""
    return OAUTH2_SCOPES


@pytest.fixture(name="token_entry")
def mock_token_entry(expires_at: int, scopes: list[str]) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "access_token": FAKE_ACCESS_TOKEN,
        "refresh_token": FAKE_REFRESH_TOKEN,
        "scope": " ".join(scopes),
        "type": "Bearer",
        "expires_at": expires_at,
        "expires_in": EXPIRES_IN,
    }


@pytest.fixture(name="config_entry_id")
def mock_config_entry_id() -> str | None:
    """Provide a json fixture file to load for list media item api responses."""
    return CONFIG_ENTRY_ID


@pytest.fixture(name="config_entry")
def mock_config_entry(
    config_entry_id: str, token_entry: dict[str, Any]
) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=config_entry_id,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
        },
        title="Account Name",
    )


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture(name="fixture_name")
def mock_fixture_name() -> str | None:
    """Provide a json fixture file to load for list media item api responses."""
    return None


@pytest.fixture(name="user_identifier")
def mock_user_identifier() -> str | None:
    """Provide a json fixture file to load for list media item api responses."""
    return USER_IDENTIFIER


@pytest.fixture(name="api_error")
def mock_api_error() -> Exception | None:
    """Provide a json fixture file to load for list media item api responses."""
    return None


@pytest.fixture(name="mock_api")
def mock_client_api(
    fixture_name: str,
    user_identifier: str,
    api_error: Exception,
) -> Generator[Mock, None, None]:
    """Set up fake Google Photos API responses from fixtures."""
    mock_api = AsyncMock(GooglePhotosLibraryApi, autospec=True)
    mock_api.get_user_info.return_value = UserInfoResult(
        id=user_identifier,
        name="Test Name",
        email="test.name@gmail.com",
    )

    responses = load_json_array_fixture(fixture_name, DOMAIN) if fixture_name else []

    async def list_media_items(
        *args: Any,
    ) -> AsyncGenerator[ListMediaItemResult, None, None]:
        for response in responses:
            mock_list_media_items = Mock(ListMediaItemResult)
            mock_list_media_items.media_items = [
                MediaItem.from_dict(media_item) for media_item in response["mediaItems"]
            ]
            yield mock_list_media_items

    mock_api.list_media_items.return_value.__aiter__ = list_media_items
    mock_api.list_media_items.return_value.__anext__ = list_media_items
    mock_api.list_media_items.side_effect = api_error

    # Mock a point lookup by reading contents of the fixture above
    async def get_media_item(media_item_id: str, **kwargs: Any) -> Mock:
        for response in responses:
            for media_item in response["mediaItems"]:
                if media_item["id"] == media_item_id:
                    return MediaItem.from_dict(media_item)
        return None

    mock_api.get_media_item = get_media_item

    # Emulate an async iterator for returning pages of response objects. We just
    # return a single page.

    async def list_albums(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[ListAlbumResult, None, None]:
        mock_list_album_result = Mock(ListAlbumResult)
        mock_list_album_result.albums = [
            Album.from_dict(album)
            for album in load_json_object_fixture("list_albums.json", DOMAIN)["albums"]
        ]
        yield mock_list_album_result

    mock_api.list_albums.return_value.__aiter__ = list_albums
    mock_api.list_albums.return_value.__anext__ = list_albums
    mock_api.list_albums.side_effect = api_error
    return mock_api


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: Mock,
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.google_photos.GooglePhotosLibraryApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
