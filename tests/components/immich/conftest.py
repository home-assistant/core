"""Common fixtures for the Immich tests."""

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aioimmich import (
    ImmichAlbums,
    ImmichAssests,
    ImmichPeople,
    ImmichSearch,
    ImmichServer,
    ImmichTags,
    ImmichUsers,
)
from aioimmich.albums.models import ImmichAddAssetsToAlbumResponse
from aioimmich.assets.models import ImmichAssetUploadResponse
from aioimmich.people.models import ImmichPerson
from aioimmich.server.models import (
    ImmichServerAbout,
    ImmichServerStatistics,
    ImmichServerStorage,
    ImmichServerVersionCheck,
)
from aioimmich.tags.models import ImmichTag
from aioimmich.users.models import ImmichUserObject
import pytest

from homeassistant.components.immich.const import DOMAIN
from homeassistant.components.media_source import PlayMedia
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.aiohttp import MockStreamReaderChunked

from .const import (
    MOCK_ALBUM_WITH_ASSETS,
    MOCK_ALBUM_WITHOUT_ASSETS,
    MOCK_PEOPLE_ASSETS,
    MOCK_TAGS_ASSETS,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.immich.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_API_KEY: "api_key",
            CONF_VERIFY_SSL: True,
        },
        unique_id="e7ef5713-9dab-4bd4-b899-715b0ca4379e",
        title="Someone",
    )


@pytest.fixture
def mock_immich_albums() -> AsyncMock:
    """Mock the Immich server."""
    mock = AsyncMock(spec=ImmichAlbums)
    mock.async_get_all_albums.return_value = [MOCK_ALBUM_WITHOUT_ASSETS]
    mock.async_get_album_info.return_value = MOCK_ALBUM_WITH_ASSETS
    mock.async_add_assets_to_album.return_value = [
        ImmichAddAssetsToAlbumResponse.from_dict(
            {"id": "abcdef-0123456789", "success": True}
        )
    ]

    return mock


@pytest.fixture
def mock_immich_assets() -> AsyncMock:
    """Mock the Immich server."""
    mock = AsyncMock(spec=ImmichAssests)
    mock.async_view_asset.return_value = b"xxxx"
    mock.async_play_video_stream.return_value = MockStreamReaderChunked(b"xxxx")
    mock.async_upload_asset.return_value = ImmichAssetUploadResponse.from_dict(
        {"id": "abcdef-0123456789", "status": "created"}
    )
    return mock


@pytest.fixture
def mock_immich_people() -> AsyncMock:
    """Mock the Immich server."""
    mock = AsyncMock(spec=ImmichPeople)
    mock.async_get_all_people.return_value = [
        ImmichPerson.from_dict(
            {
                "id": "6176838a-ac5a-4d1f-9a35-91c591d962d8",
                "name": "Me",
                "birthDate": None,
                "thumbnailPath": "upload/thumbs/e7ef5713-9dab-4bd4-b899-715b0ca4379e/61/76/6176838a-ac5a-4d1f-9a35-91c591d962d8.jpeg",
                "isHidden": False,
                "isFavorite": False,
                "updatedAt": "2025-05-11T11:07:41.651Z",
            }
        ),
        ImmichPerson.from_dict(
            {
                "id": "3e66aa4a-a4a8-41a4-86fe-2ae5e490078f",
                "name": "I",
                "birthDate": None,
                "thumbnailPath": "upload/thumbs/e7ef5713-9dab-4bd4-b899-715b0ca4379e/3e/66/3e66aa4a-a4a8-41a4-86fe-2ae5e490078f.jpeg",
                "isHidden": False,
                "isFavorite": False,
                "updatedAt": "2025-05-19T22:10:21.953Z",
            }
        ),
        ImmichPerson.from_dict(
            {
                "id": "a3c83297-684a-4576-82dc-b07432e8a18f",
                "name": "Myself",
                "birthDate": None,
                "thumbnailPath": "upload/thumbs/e7ef5713-9dab-4bd4-b899-715b0ca4379e/a3/c8/a3c83297-684a-4576-82dc-b07432e8a18f.jpeg",
                "isHidden": False,
                "isFavorite": False,
                "updatedAt": "2025-05-12T21:07:04.044Z",
            }
        ),
    ]
    mock.async_get_person_thumbnail.return_value = b"yyyy"
    return mock


@pytest.fixture
def mock_immich_search() -> AsyncMock:
    """Mock the Immich server."""
    mock = AsyncMock(spec=ImmichSearch)
    mock.async_get_all_by_person_ids.return_value = MOCK_PEOPLE_ASSETS
    mock.async_get_all_by_tag_ids.return_value = MOCK_TAGS_ASSETS
    return mock


@pytest.fixture
def mock_immich_server() -> AsyncMock:
    """Mock the Immich server."""
    mock = AsyncMock(spec=ImmichServer)
    mock.async_get_about_info.return_value = ImmichServerAbout.from_dict(
        {
            "version": "v1.134.0",
            "versionUrl": "https://github.com/immich-app/immich/releases/tag/v1.134.0",
            "licensed": False,
            "build": "15281783550",
            "buildUrl": "https://github.com/immich-app/immich/actions/runs/15281783550",
            "buildImage": "v1.134.0",
            "buildImageUrl": "https://github.com/immich-app/immich/pkgs/container/immich-server",
            "repository": "immich-app/immich",
            "repositoryUrl": "https://github.com/immich-app/immich",
            "sourceRef": "v1.134.0",
            "sourceCommit": "58ae77ec9204a2e43a8cb2f1fd27482af40d0891",
            "sourceUrl": "https://github.com/immich-app/immich/commit/58ae77ec9204a2e43a8cb2f1fd27482af40d0891",
            "nodejs": "v22.14.0",
            "exiftool": "13.00",
            "ffmpeg": "7.0.2-9",
            "libvips": "8.16.1",
            "imagemagick": "7.1.1-47",
        }
    )
    mock.async_get_storage_info.return_value = ImmichServerStorage.from_dict(
        {
            "diskSize": "294.2 GiB",
            "diskUse": "142.9 GiB",
            "diskAvailable": "136.3 GiB",
            "diskSizeRaw": 315926315008,
            "diskUseRaw": 153400406016,
            "diskAvailableRaw": 146403004416,
            "diskUsagePercentage": 48.56,
        }
    )
    mock.async_get_server_statistics.return_value = ImmichServerStatistics.from_dict(
        {
            "photos": 27038,
            "videos": 1836,
            "usage": 119525451912,
            "usagePhotos": 54291170551,
            "usageVideos": 65234281361,
            "usageByUser": [
                {
                    "userId": "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
                    "userName": "admin",
                    "photos": 27038,
                    "videos": 1836,
                    "usage": 119525451912,
                    "usagePhotos": 54291170551,
                    "usageVideos": 65234281361,
                    "quotaSizeInBytes": None,
                }
            ],
        }
    )
    mock.async_get_version_check.return_value = ImmichServerVersionCheck.from_dict(
        {
            "checkedAt": "2025-06-21T16:35:10.352Z",
            "releaseVersion": "v1.135.3",
        }
    )
    return mock


@pytest.fixture
def mock_immich_tags() -> AsyncMock:
    """Mock the Immich server."""
    mock = AsyncMock(spec=ImmichTags)
    mock.async_get_all_tags.return_value = [
        ImmichTag.from_dict(
            {
                "id": "67301cb8-cb73-4e8a-99e9-475cb3f7e7b5",
                "name": "Halloween",
                "value": "Halloween",
                "createdAt": "2025-05-12T20:00:45.220Z",
                "updatedAt": "2025-05-12T20:00:47.224Z",
            },
        ),
        ImmichTag.from_dict(
            {
                "id": "69bd487f-dc1e-4420-94c6-656f0515773d",
                "name": "Holidays",
                "value": "Holidays",
                "createdAt": "2025-05-12T20:00:49.967Z",
                "updatedAt": "2025-05-12T20:00:55.575Z",
            },
        ),
    ]
    return mock


@pytest.fixture
def mock_immich_user() -> AsyncMock:
    """Mock the Immich server."""
    mock = AsyncMock(spec=ImmichUsers)
    mock.async_get_my_user.return_value = ImmichUserObject.from_dict(
        {
            "id": "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "email": "user@immich.local",
            "name": "user",
            "profileImagePath": "",
            "avatarColor": "primary",
            "profileChangedAt": "2025-05-11T10:07:46.866Z",
            "storageLabel": "user",
            "shouldChangePassword": True,
            "isAdmin": True,
            "createdAt": "2025-05-11T10:07:46.866Z",
            "deletedAt": None,
            "updatedAt": "2025-05-18T00:59:55.547Z",
            "oauthId": "",
            "quotaSizeInBytes": None,
            "quotaUsageInBytes": 119526467534,
            "status": "active",
            "license": None,
        }
    )
    return mock


@pytest.fixture
async def mock_immich(
    mock_immich_albums: AsyncMock,
    mock_immich_assets: AsyncMock,
    mock_immich_people: AsyncMock,
    mock_immich_search: AsyncMock,
    mock_immich_server: AsyncMock,
    mock_immich_tags: AsyncMock,
    mock_immich_user: AsyncMock,
) -> AsyncGenerator[AsyncMock]:
    """Mock the Immich API."""
    with (
        patch("homeassistant.components.immich.Immich", autospec=True) as mock_immich,
        patch("homeassistant.components.immich.config_flow.Immich", new=mock_immich),
    ):
        client = mock_immich.return_value
        client.albums = mock_immich_albums
        client.assets = mock_immich_assets
        client.people = mock_immich_people
        client.search = mock_immich_search
        client.server = mock_immich_server
        client.tags = mock_immich_tags
        client.users = mock_immich_user
        yield client


@pytest.fixture
async def mock_non_admin_immich(mock_immich: AsyncMock) -> AsyncMock:
    """Mock the Immich API."""
    mock_immich.users.async_get_my_user.return_value.is_admin = False
    return mock_immich


@pytest.fixture
def mock_media_source() -> Generator[MagicMock]:
    """Mock the media source."""
    with patch(
        "homeassistant.components.immich.services.async_resolve_media",
        return_value=PlayMedia(
            url="media-source://media_source/local/screenshot.jpg",
            mime_type="image/jpeg",
            path=Path("/media/screenshot.jpg"),
        ),
    ) as mock_media:
        yield mock_media


@pytest.fixture
async def setup_media_source(hass: HomeAssistant) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})
