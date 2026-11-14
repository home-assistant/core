"""Fixtures for PowerShades tests."""

from collections.abc import Generator
import struct
from unittest.mock import AsyncMock, MagicMock, patch

from pyowershades import OP_GET_STATUS, build_packet
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.powershades.const import DOMAIN
from homeassistant.const import CONF_HOST

TEST_IP = "192.168.1.50"
TEST_SERIAL = 12345
TEST_NAME = "Bedroom Shade"


def status_packet(position: int = 50, battery_mv: int = 3700) -> bytes:
    """Build a Get Status reply packet with the given position and battery."""
    # position, tilt, memory, battery_mv, time, cycles, stalls, temperature,
    # raw position, raw tilt
    payload = struct.pack(
        "<hhHHIIIhII", position, 0, 0, battery_mv, 0, 0, 0, 20, position, 0
    )
    return build_packet(OP_GET_STATUS, payload=payload)


@pytest.fixture(autouse=True)
def mock_discover_devices() -> Generator[AsyncMock]:
    """Mock broadcast discovery, returning no devices by default.

    This also keeps the periodic background scan off real sockets.
    """
    with (
        patch(
            "homeassistant.components.powershades.discovery.async_discover_devices",
            return_value=[],
        ) as mock,
        patch(
            "homeassistant.components.powershades.config_flow.async_discover_devices",
            new=mock,
        ),
    ):
        yield mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Bypass full entry setup, e.g. for config flow tests."""
    with patch(
        "homeassistant.components.powershades.async_setup_entry", return_value=None
    ) as mock:
        yield mock


@pytest.fixture
def mock_device_info() -> Generator[AsyncMock]:
    """Mock probing a device for its serial number and name."""
    with patch(
        "homeassistant.components.powershades.config_flow.async_get_device_info",
        return_value={"serial": TEST_SERIAL, "name": TEST_NAME, "model": 1},
    ) as mock:
        yield mock


@pytest.fixture
def mock_powershades_connection() -> Generator[MagicMock]:
    """Mock the UDP connection to a shade that is 50% open."""
    with patch(
        "homeassistant.components.powershades.PowerShadesConnection", autospec=True
    ) as mock_connection_class:
        connection = mock_connection_class.return_value
        connection.async_request.return_value = status_packet()
        yield connection


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a PowerShades config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_IP,
            "serial": TEST_SERIAL,
            "name": TEST_NAME,
            "model": 1,
            "mac": "d8:3a:f5:11:22:33",
        },
        unique_id=str(TEST_SERIAL),
        entry_id="01JPOWERSHADESTESTENTRY000",
    )
