"""Fixtures for the LibreSync tests."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from aiolibresync import (
    DeviceState,
    DiscoveredDevice,
    LibreSyncClient,
    NowPlaying,
    PlayState,
    Source,
)
import pytest

from homeassistant.components.libresync.const import CONF_SERIAL, CONF_UDN, DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

HOST = "192.168.1.50"
UDN = "uuid:1a2b3c4d-5e6f-11f0-9193-0123456789ab"
SERIAL = "FAKE0SERIAL000000000"

STATE = DeviceState(
    available=True,
    power=True,
    volume=28,
    muted=False,
    source=Source(index=0, name="Streaming"),
    # The hub's own order, which is not sorted by index.
    sources=(
        Source(index=1, name="USB"),
        Source(index=6, name="HDMI"),
        Source(index=0, name="Streaming"),
    ),
    play_state=PlayState.PAUSED,
    audio_state=PlayState.PAUSED,
    model="Stereo Hub",
    serial=SERIAL,
    now_playing=NowPlaying(
        title="Track",
        artist="Artist",
        album="Album",
        duration_ms=315000,
        app="TIDAL",
    ),
)

FOUND = DiscoveredDevice(
    host=HOST,
    udn=UDN,
    name="Stereo",
    model="LibreWireless",
    manufacturer="LibreWireless",
    description_url=f"http://{HOST}:38400/description.xml",
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.libresync.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry keyed on the serial."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Stereo",
        unique_id=SERIAL,
        data={CONF_HOST: HOST, CONF_SERIAL: SERIAL, CONF_UDN: UDN},
    )


@pytest.fixture
def mock_probe() -> Generator[AsyncMock]:
    """Mock the control port probe."""
    with patch(
        "homeassistant.components.libresync.config_flow.async_probe",
        return_value=FOUND,
    ) as probe:
        yield probe


@pytest.fixture
def mock_probe_control() -> Generator[AsyncMock]:
    """Mock the control port check of a discovered hub."""
    with patch(
        "homeassistant.components.libresync.config_flow.async_probe_control",
        return_value=True,
    ) as probe:
        yield probe


@pytest.fixture
def mock_read_serial() -> Generator[AsyncMock]:
    """Mock reading the factory serial."""
    with patch(
        "homeassistant.components.libresync.config_flow.async_read_serial",
        return_value=SERIAL,
    ) as read_serial:
        yield read_serial


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock a client that never opens a socket.

    `subscribe` keeps the callbacks, so `push` can publish a state the way the
    hub would.
    """
    client = create_autospec(LibreSyncClient, instance=True)
    client.state = STATE
    client.subscribers = []

    def subscribe(callback: Callable[[DeviceState], None]) -> Callable[[], None]:
        client.subscribers.append(callback)
        return lambda: client.subscribers.remove(callback)

    client.subscribe = subscribe
    with patch(
        "homeassistant.components.libresync.LibreSyncClient", return_value=client
    ):
        yield client


def push(client: MagicMock, state: DeviceState) -> None:
    """Publish a new state to every subscriber."""
    client.state = state
    for callback in list(client.subscribers):
        callback(state)
