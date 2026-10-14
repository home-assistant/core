"""Configure iCloud tests."""

from collections.abc import Generator, Iterator
from typing import Any
from unittest.mock import patch

from pyicloud.services.photos import AlbumContainer, PhotoAlbumFolder, PhotoAsset
import pytest

from homeassistant.components.icloud.const import DOMAIN

from .const import DEVICE, USER_INFO

from tests.common import AsyncMock, MockConfigEntry
from tests.typing import MagicMock


class MockAppleDevice:
    """Mock Apple device implementing .status() used by the account."""

    def __init__(self, status: dict[str, Any]) -> None:
        """Initialize the device with its Apple status payload."""
        self._status = status

    def status(self, _keys: Any) -> dict[str, Any]:
        """Return the status payload, whatever subset the account asks for."""
        return self._status

    def __getitem__(self, key: str) -> Any:
        """Allow indexing to proxy into the raw status dict."""
        return self._status.get(key)


class MockDevicesContainer:
    """Mock devices container, iterable and indexable."""

    def __init__(
        self, userinfo: dict[str, Any], devices: list[MockAppleDevice]
    ) -> None:
        """Initialize with the user info and the devices Apple reports."""
        self.user_info = userinfo
        self._devices = devices
        self.refresh_calls: list[bool] = []

    def refresh(self, locate: bool = False) -> None:
        """Record refresh calls made by the account."""
        self.refresh_calls.append(locate)

    def __iter__(self) -> Iterator[MockAppleDevice]:
        """Iterate returns device objects (each must have .status(...))."""
        return iter(self._devices)

    def __len__(self) -> int:
        """Return number of devices."""
        return len(self._devices)

    def __getitem__(self, idx: int) -> Any:
        """Indexing returns device object (which must have .status(...))."""
        dev = self._devices[idx]
        if hasattr(dev, "status"):
            return dev.status(None)
        return dev


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
                spec=PhotoAlbumFolder, id="folder_id1", title="My Folder 1", albums=[]
            ),
            MagicMock(
                id="album_id1",
                title="All Photos",
                photos=[
                    MagicMock(
                        spec=PhotoAsset,
                        id="photo_id1",
                        filename="My Photo 1.JPG",
                        item_type="image",
                        versions={
                            "original": MagicMock(
                                size=123456,
                                width=4000,
                                height=3000,
                            )
                        },
                    ),
                    MagicMock(
                        spec=PhotoAsset,
                        id="photo_id2",
                        filename="My Photo 2.heic",
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
                        filename="My Photo 2.heic",
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
            MagicMock(
                id="stream_id2",
                title="Random Stream",
                photos=[
                    MagicMock(
                        spec=PhotoAsset,
                        id="shared_id3",
                        filename="My Unknown file.xyz",
                        item_type="unknown",
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


@pytest.fixture(name="icloud_devices")
def mock_icloud_devices() -> list[MockAppleDevice]:
    """Return the devices the mocked account reports to the integration."""
    return [MockAppleDevice(DEVICE)]


@pytest.fixture(name="mock_icloud_service")
def mock_icloud_service(
    icloud_devices: list[MockAppleDevice],
) -> Generator[MagicMock]:
    """Mock the pyicloud client the account logs in with."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService",
    ) as service_mock:
        service_instance = MagicMock()
        service_instance.requires_2fa = False
        service_instance.devices = MockDevicesContainer(USER_INFO, icloud_devices)

        service_mock.return_value = service_instance
        yield service_mock
