"""Configure iCloud tests."""

from collections.abc import Awaitable, Callable, Generator, Iterator
from typing import Any
from unittest.mock import patch

from pyicloud.services.photos import AlbumContainer, PhotoAlbumFolder, PhotoAsset
import pytest
from pytest_homeassistant.common import AsyncMock, MockConfigEntry
from pytest_homeassistant.typing import MagicMock

from homeassistant.components.icloud.const import (
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    CONF_WITH_FAMILY,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import DEVICE, USER_INFO


class MockAppleDevice:
    """Mock an Apple device with the API surface the account uses."""

    def __init__(self, status: dict[str, Any]) -> None:
        """Initialize the device with its status payload."""
        self._status = status
        self.play_sound = MagicMock()

    def _feature(self, key: str) -> bool:
        """Return whether the device reports the feature flag."""
        return bool((self._status.get("features") or {}).get(key, False))

    def status(self, additional: list[str] | None = None) -> dict[str, Any]:
        """Return the status payload, whatever subset the account asks for."""
        return self._status

    def __getitem__(self, key: str) -> Any:
        """Allow indexing to proxy into the raw status dict."""
        return self._status.get(key)

    @property
    def erase_available(self) -> bool:
        """Return whether the device can be remotely erased."""
        return self._feature("WIP")

    @property
    def location_available(self) -> bool:
        """Return whether the device reports a location."""
        return self._feature("LOC") and self._status.get("location") is not None

    @property
    def lost_mode_available(self) -> bool:
        """Return whether the device supports lost mode."""
        return bool(self._status.get("lostModeCapable", False))


class MockDevicesContainer:
    """Mock the Find My devices container."""

    def __init__(
        self,
        userinfo: dict[str, Any] | None = None,
        devices: list[Any] | None = None,
    ) -> None:
        """Initialize with the user info and the devices Apple reports."""
        self.user_info = USER_INFO if userinfo is None else userinfo
        self.devices: list[Any] = devices if devices is not None else []
        self.refresh_calls: list[bool] = []

    def add(self, status: dict[str, Any]) -> MockAppleDevice:
        """Add a device reporting the given status payload."""
        device = MockAppleDevice(status)
        self.devices.append(device)
        return device

    def refresh(self, locate: bool = True) -> None:
        """Record refresh calls made by the account."""
        self.refresh_calls.append(locate)

    def __iter__(self) -> Iterator[MockAppleDevice]:
        """Iterate returns device objects (each must have .status(...))."""
        return iter(
            device if hasattr(device, "status") else MockAppleDevice(device)
            for device in self.devices
        )

    def __len__(self) -> int:
        """Return number of devices."""
        return len(self.devices)

    def __getitem__(self, idx: int) -> Any:
        """Indexing returns the status of the indexed device."""
        device = self.devices[idx]
        if hasattr(device, "status"):
            return device.status(None)
        return device


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


@pytest.fixture(name="devices_config_entry")
def mock_devices_config_entry() -> MockConfigEntry:
    """Create a mock config entry for tests that set up real devices."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_account_id",
        title="Test iCloud Account",
        data={
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_pass",
            CONF_WITH_FAMILY: False,
            CONF_MAX_INTERVAL: 15,
            CONF_GPS_ACCURACY_THRESHOLD: 500,
        },
    )


@pytest.fixture(name="icloud_service")
def icloud_service_fixture() -> Generator[MagicMock]:
    """Mock PyiCloudService with a device container the test fills in."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service = service_mock.return_value
        service.requires_2fa = False
        service.devices = MockDevicesContainer()
        yield service


@pytest.fixture(name="setup_entry")
def mock_setup_entry(
    hass: HomeAssistant, devices_config_entry: MockConfigEntry
) -> Callable[[Platform], Awaitable[None]]:
    """Return a helper that sets up the entry with a single platform."""

    async def _setup(platform: Platform) -> None:
        devices_config_entry.add_to_hass(hass)
        with patch("homeassistant.components.icloud.PLATFORMS", [platform]):
            await hass.config_entries.async_setup(devices_config_entry.entry_id)
            await hass.async_block_till_done(wait_background_tasks=True)

    return _setup
