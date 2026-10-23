"""Fixtures for the Openhome integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from openhomedevice.device import Device
import pytest

from homeassistant.components.openhome.const import DOMAIN
from homeassistant.const import CONF_HOST, Platform

from tests.common import MockConfigEntry

HOST = "http://localhost"

TRACK_INFO = {
    "albumArtwork": "http://localhost/album.jpg",
    "albumTitle": "album_title",
    "artist": ["artist"],
    "title": "title",
    "uri": "http://localhost/track.flac",
}

SOURCES = [
    {"index": 0, "name": "Playlist", "type": "Playlist"},
    {"index": 1, "name": "Radio", "type": "Radio"},
]

# The device coroutines the actions drive, referenced from the library so a
# rename upstream fails the tests rather than leaving an action uncovered.
ACTION_METHODS = (
    Device.set_standby,
    Device.play,
    Device.pause,
    Device.stop,
    Device.skip,
    Device.increase_volume,
    Device.decrease_volume,
    Device.set_volume,
    Device.set_mute,
    Device.set_source,
    Device.play_media,
    Device.invoke_pin,
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST}, unique_id="uuid")


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms to load; override per module or per test."""
    return []


@pytest.fixture(autouse=True)
def patch_platforms(platforms: list[Platform]) -> Generator[None]:
    """Load only the platforms the test asks for."""
    with patch("homeassistant.components.openhome.PLATFORMS", platforms):
        yield


@pytest.fixture
def mock_device_class() -> Generator[MagicMock]:
    """Return the patched Openhome Device class."""
    with patch("homeassistant.components.openhome.Device", MagicMock()) as mock_class:
        device = mock_class.return_value
        device.init = AsyncMock()
        device.uuid = MagicMock(return_value="uuid")
        device.manufacturer = MagicMock(return_value="manufacturer")
        device.model_name = MagicMock(return_value="model_name")
        device.friendly_name = MagicMock(return_value="friendly_name")
        device.volume_enabled = True
        device.pins_enabled = True
        device.room = AsyncMock(return_value="room")
        device.track_info = AsyncMock(return_value={})
        device.volume = AsyncMock(return_value=50)
        device.is_muted = AsyncMock(return_value=False)
        device.sources = AsyncMock(return_value=SOURCES)
        device.source = AsyncMock(return_value=SOURCES[0])
        device.is_in_standby = AsyncMock(return_value=False)
        device.transport_state = AsyncMock(return_value="Playing")
        device.software_status = AsyncMock(return_value=None)
        device.update_firmware = AsyncMock()
        for method in ACTION_METHODS:
            setattr(device, method.__name__, AsyncMock())
        yield mock_class


@pytest.fixture
def mock_device(mock_device_class: MagicMock) -> MagicMock:
    """Return a mocked Openhome device that polls successfully."""
    return mock_device_class.return_value
