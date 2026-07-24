"""Fixtures for PowerShades tests."""

import struct
from unittest.mock import AsyncMock, patch

from pyowershades import (
    OP_GET_SHADE_NAME,
    OP_GET_STATUS,
    PowerShadesConnection,
    build_packet,
)
import pytest

from homeassistant.components.powershades.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_IP = "192.168.1.50"
TEST_SERIAL = 12345
TEST_NAME = "Bedroom Shade"


@pytest.fixture(autouse=True)
def mock_background_discovery():
    """Prevent periodic background discovery from touching real sockets."""
    with patch(
        "homeassistant.components.powershades.discovery.async_discover_devices",
        return_value=[],
    ):
        yield


@pytest.fixture
def mock_setup_entry():
    """Bypass full entry setup, e.g. for config flow tests."""
    with patch(
        "homeassistant.components.powershades.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_discover_devices():
    """Mock broadcast discovery, returning no devices by default."""
    with patch(
        "homeassistant.components.powershades.config_flow.async_discover_devices",
        return_value=[],
    ) as mock:
        yield mock


@pytest.fixture
def mock_device_info():
    """Mock probing a device for its serial number and name."""
    with patch(
        "homeassistant.components.powershades.config_flow.async_get_device_info",
        return_value={"serial": 12345, "name": "Bedroom Shade", "model": 1},
    ) as mock:
        yield mock


def status_packet(position: int = 50, battery_mv: int = 3700) -> bytes:
    """Build a Get Status reply packet with the given position and battery."""
    payload = struct.pack(
        "<hhHHIIIhII", position, 0, 0, battery_mv, 0, 0, 0, 20, position, 0
    )
    return build_packet(OP_GET_STATUS, payload=payload)


def shade_name_packet(name: str) -> bytes:
    """Build a Get PoE Shade Name reply packet."""
    payload = b"\x00" + name.encode("ascii").ljust(50, b"\x00")
    return build_packet(OP_GET_SHADE_NAME, payload=payload)


@pytest.fixture
def mock_connection():
    """Mock the UDP connection so setup never touches real sockets."""

    async def fake_request(op, payload=b"", timeout=None, retries=None):
        if op == OP_GET_STATUS:
            return status_packet()
        if op == OP_GET_SHADE_NAME:
            return shade_name_packet(TEST_NAME)
        return build_packet(op)

    with (
        patch.object(PowerShadesConnection, "async_connect", AsyncMock()),
        patch.object(
            PowerShadesConnection,
            "async_request",
            AsyncMock(side_effect=fake_request),
        ),
        patch.object(PowerShadesConnection, "close"),
    ):
        yield


@pytest.fixture
async def config_entry(hass: HomeAssistant, mock_connection):
    """Set up a loaded PowerShades config entry with a mocked connection."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "ip": TEST_IP,
            "serial": TEST_SERIAL,
            "name": TEST_NAME,
            "model": 1,
            "mac": "d8:3a:f5:11:22:33",
        },
        unique_id=str(TEST_SERIAL),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
