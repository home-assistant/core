"""Common fixtures for the Immich tests."""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

from aioimmich import ImmichAlbums, ImmichAssests, ImmichServer, ImmichUsers
from aioimmich.server.models import (
    ImmichServerAbout,
    ImmichServerStatistics,
    ImmichServerStorage,
)
from aioimmich.users.models import AvatarColor, ImmichUser, UserStatus
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
    return mock


@pytest.fixture
def mock_immich_server() -> AsyncMock:
    """Mock the Immich server."""
    mock = AsyncMock(spec=ImmichServer)
    mock.async_get_about_info.return_value = ImmichServerAbout(
        "v1.132.3",
        "some_url",
        False,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    mock.async_get_storage_info.return_value = ImmichServerStorage(
        "294.2 GiB",
        "142.9 GiB",
        "136.3 GiB",
        315926315008,
        153400434688,
        146402975744,
        48.56,
    )
    mock.async_get_server_statistics.return_value = ImmichServerStatistics(
        27038, 1836, 119525451912, 54291170551, 65234281361
    )
    return mock


@pytest.fixture
def mock_immich_user() -> AsyncMock:
    """Mock the Immich server."""
    mock = AsyncMock(spec=ImmichUsers)
    mock.async_get_my_user.return_value = ImmichUser(
        "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
        "user@immich.local",
        "user",
        "",
        AvatarColor.PRIMARY,
        datetime.fromisoformat("2025-05-11T10:07:46.866Z"),
        "user",
        False,
        True,
        datetime.fromisoformat("2025-05-11T10:07:46.866Z"),
        None,
        None,
        "",
        None,
        None,
        UserStatus.ACTIVE,
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
