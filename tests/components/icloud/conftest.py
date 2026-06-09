"""Configure iCloud tests."""

from collections.abc import Generator
from unittest.mock import patch

from pyicloud.services.photos import AlbumContainer, PhotoAsset
import pytest

from homeassistant.components.icloud.const import DOMAIN

from tests.common import AsyncMock, MockConfigEntry
from tests.typing import MagicMock


@pytest.fixture(autouse=True)
def icloud_not_create_dir():
    """Mock component setup."""
    with patch(
        "homeassistant.components.icloud.config_flow.os.path.exists", return_value=True
    ):
        yield


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
        client.photo_cache = None

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
