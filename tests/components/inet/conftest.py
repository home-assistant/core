"""Common fixtures for the iNet Radio tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.inet.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.100"
MOCK_MAC = "78:c4:0e:01:22:f4"
MOCK_SERIAL = "78C40E0122F4"
MOCK_UNIQUE_ID = "78:c4:0e:01:22:f4"
MOCK_NAME = "Living Room Radio"
MOCK_MODEL_DESCRIPTION = "Busch-Jaeger Internet Radio 8216U"


def _create_mock_radio(
    ip: str = MOCK_HOST,
    name: str = MOCK_NAME,
    mac: str = MOCK_MAC,
    unique_id: str = MOCK_UNIQUE_ID,
) -> MagicMock:
    """Create a mock Radio object."""
    radio = MagicMock()
    radio.ip = ip
    radio.name = name
    radio.mac = mac
    radio.serial = "78C40E0122F4"
    radio.sw_version = "02.06"
    radio.unique_id = unique_id
    radio.power = False
    radio.volume = 10
    radio.muted = False
    radio.available = True
    radio.playing_mode = ""
    radio.playing_station_name = ""
    radio.playing_station_url = ""
    radio.playing_station_id = None
    radio.energy_mode = "PREMIUM"
    radio.stations = []
    radio._callbacks = []

    def register_callback(cb):
        radio._callbacks.append(cb)

        def unsub():
            if cb in radio._callbacks:
                radio._callbacks.remove(cb)

        return unsub

    radio.register_callback = register_callback
    return radio


def _create_mock_station(channel: int, name: str, url: str) -> MagicMock:
    """Create a mock Station object."""
    station = MagicMock()
    station.channel = channel
    station.name = name
    station.url = url
    return station


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        data={CONF_HOST: MOCK_HOST},
        unique_id=MOCK_UNIQUE_ID,
    )


@pytest.fixture
def mock_radio() -> MagicMock:
    """Create a mock Radio."""
    return _create_mock_radio()


@pytest.fixture
def mock_manager(mock_radio: MagicMock) -> Generator[AsyncMock]:
    """Create a mock RadioManager."""
    with patch("homeassistant.components.inet.RadioManager", autospec=True) as mock_cls:
        manager = mock_cls.return_value
        manager.start = AsyncMock()
        manager.stop = AsyncMock()
        manager.connect = AsyncMock(return_value=mock_radio)
        manager.discover = AsyncMock()
        manager.turn_on = AsyncMock()
        manager.turn_off = AsyncMock()
        manager.set_volume = AsyncMock()
        manager.volume_up = AsyncMock()
        manager.volume_down = AsyncMock()
        manager.mute = AsyncMock()
        manager.unmute = AsyncMock()
        manager.play_station = AsyncMock()
        manager.play_aux = AsyncMock()
        manager.play_upnp = AsyncMock()
        manager.request_playing_mode = AsyncMock()
        manager.radios = {mock_radio.ip: mock_radio}
        yield manager


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with (
        patch("homeassistant.components.inet.async_setup", return_value=True),
        patch(
            "homeassistant.components.inet.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        yield mock_setup_entry
