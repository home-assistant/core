"""Common fixtures for the Immich tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

from aioimmich import ImmichAlbums, ImmichAssests, ImmichServer, ImmichUsers
from aioimmich.server.models import (
    ImmichServerAbout,
    ImmichServerStatistics,
    ImmichServerStorage,
)
from aioimmich.users.models import ImmichUserObject
import pytest

from homeassistant.components.immich.const import DOMAIN
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

from .const import MOCK_ALBUM_WITH_ASSETS, MOCK_ALBUM_WITHOUT_ASSETS

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
    return mock


@pytest.fixture
def mock_immich_assets() -> AsyncMock:
    """Mock the Immich server."""
    mock = AsyncMock(spec=ImmichAssests)
    mock.async_view_asset.return_value = b"xxxx"
    mock.async_play_video_stream.return_value = MockStreamReaderChunked(b"xxxx")
    return mock


@pytest.fixture
def mock_immich_server() -> AsyncMock:
    """Mock the Immich server."""
    mock = AsyncMock(spec=ImmichServer)
    mock.async_get_about_info.return_value = ImmichServerAbout.from_dict(
        {
            "version": "v1.132.3",
            "versionUrl": "https://github.com/immich-app/immich/releases/tag/v1.132.3",
            "licensed": False,
            "build": "14709928600",
            "buildUrl": "https://github.com/immich-app/immich/actions/runs/14709928600",
            "buildImage": "v1.132.3",
            "buildImageUrl": "https://github.com/immich-app/immich/pkgs/container/immich-server",
            "repository": "immich-app/immich",
            "repositoryUrl": "https://github.com/immich-app/immich",
            "sourceRef": "v1.132.3",
            "sourceCommit": "02994883fe3f3972323bb6759d0170a4062f5236",
            "sourceUrl": "https://github.com/immich-app/immich/commit/02994883fe3f3972323bb6759d0170a4062f5236",
            "nodejs": "v22.14.0",
            "exiftool": "13.00",
            "ffmpeg": "7.0.2-7",
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
    mock_immich_server: AsyncMock,
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
        client.server = mock_immich_server
        client.users = mock_immich_user
        yield client


@pytest.fixture
async def mock_non_admin_immich(mock_immich: AsyncMock) -> AsyncMock:
    """Mock the Immich API."""
    mock_immich.users.async_get_my_user.return_value.is_admin = False
    return mock_immich


@pytest.fixture
async def setup_media_source(hass: HomeAssistant) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})
