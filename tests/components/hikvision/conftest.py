"""Common fixtures for the Hikvision tests."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass, field
import threading
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.hikvision import PLATFORMS
from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)

TEST_HOST = "192.168.1.100"
TEST_PORT = 80
TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"
TEST_DEVICE_ID = "DS-2CD2142FWD-I20170101AAAA"
TEST_DEVICE_NAME = "Front Camera"


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return PLATFORMS


@pytest.fixture(autouse=True)
async def mock_patch_platforms(platforms: list[Platform]) -> AsyncGenerator[None]:
    """Fixture to set up platforms for tests."""
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hikvision.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_DEVICE_NAME,
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
        unique_id=TEST_DEVICE_ID,
    )


@pytest.fixture
def amount_of_channels() -> int:
    """Return the default amount of video channels."""
    return 0


@pytest.fixture
def mock_channels(amount_of_channels: int) -> list[MagicMock]:
    """Return a list of mocked VideoChannel objects."""
    channels = []
    for channel_id in range(1, amount_of_channels + 1):
        channel = MagicMock()
        channel.id = channel_id
        channel.name = f"Channel {channel_id}"
        channel.enabled = True
        channels.append(channel)
    return channels


@pytest.fixture
def mock_hik_get_channels(mock_channels: list[MagicMock]) -> Generator[MagicMock]:
    """Return a mocked HikCamera."""
    with patch(
        "homeassistant.components.hikvision.get_video_channels",
    ) as hik_channels_mock:
        hik_channels_mock.return_value = mock_channels
        yield hik_channels_mock


@pytest.fixture
def mock_hikcamera(mock_hik_get_channels: MagicMock) -> Generator[MagicMock]:
    """Return a mocked HikCamera."""
    with (
        patch(
            "homeassistant.components.hikvision.HikCamera",
        ) as hikcamera_mock,
        patch(
            "homeassistant.components.hikvision.config_flow.HikCamera",
            new=hikcamera_mock,
        ),
    ):
        camera = hikcamera_mock.return_value
        camera.get_id = TEST_DEVICE_ID
        camera.get_name = TEST_DEVICE_NAME
        camera.get_type = "Camera"
        camera.current_event_states = {
            "Motion": [(True, 1)],
            "Line Crossing": [(False, 1)],
        }
        camera.fetch_attributes.return_value = (
            False,
            None,
            None,
            "2024-01-01T00:00:00Z",
            None,
        )
        camera.get_event_triggers.return_value = {}
        camera.stream_connected = True

        # pyHik 0.4.0 methods
        camera.get_channels.return_value = [1]
        camera.get_snapshot.return_value = b"fake_image_data"
        camera.get_stream_url.return_value = (
            f"rtsp://{TEST_USERNAME}:{TEST_PASSWORD}"
            f"@{TEST_HOST}:554/Streaming/Channels/1"
        )

        yield hikcamera_mock


@pytest.fixture
def mock_hik_nvr(mock_hikcamera: MagicMock) -> MagicMock:
    """Return a mocked HikCamera configured as an NVR."""
    camera = mock_hikcamera.return_value
    camera.get_type = "NVR"
    camera.current_event_states = {}
    camera.get_event_triggers.return_value = {"VMD": [1, 2]}
    return mock_hikcamera


@dataclass
class BlockingSnapshot:
    """A get_snapshot that waits to be released, as a slow camera does."""

    release: threading.Event = field(default_factory=threading.Event)
    ended: threading.Event = field(default_factory=threading.Event)
    taken: list[int] = field(default_factory=list)
    error: Exception | None = None

    def __call__(self, channel: int) -> bytes:
        """Take a picture of the channel, once released."""
        self.taken.append(channel)
        try:
            assert self.release.wait(5)
            if self.error is not None:
                raise self.error
            return f"picture {channel}".encode()
        finally:
            self.ended.set()

    async def async_wait_started(self, count: int = 1) -> None:
        """Wait for that many requests to be sent."""
        async with asyncio.timeout(5):
            while len(self.taken) < count:
                await asyncio.sleep(0)

    async def async_wait_ended(self) -> None:
        """Wait for the request to end, even with nobody waiting for its answer."""
        await self._async_wait_for(self.ended)

    @staticmethod
    async def _async_wait_for(event: threading.Event) -> None:
        async with asyncio.timeout(5):
            while not event.is_set():
                await asyncio.sleep(0)


@pytest.fixture
def blocking_snapshot(mock_hikcamera: MagicMock) -> BlockingSnapshot:
    """Make the camera answer a picture request only once released.

    Not a mock: the test harness runs a mock in the event loop, and this must run
    in the executor.
    """
    snapshot = BlockingSnapshot()
    mock_hikcamera.return_value.get_snapshot = snapshot
    return snapshot
