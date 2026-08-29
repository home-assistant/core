"""Fixtures for Arris TG2492LG integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from arris_tg2492lg import Device
import pytest

from homeassistant.components.arris_tg2492lg.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.178.1"
MOCK_PASSWORD = "password"

MOCK_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_PASSWORD: MOCK_PASSWORD,
}


def _create_device(ip: str, mac: str, hostname: str, online: bool) -> Device:
    """Create an arris_tg2492lg Device for use in tests."""
    device = Device(ip)
    device.mac = mac
    device.hostname = hostname
    device.online = online
    return device


MOCK_DEVICES = [
    _create_device("192.168.178.10", "AA:BB:CC:DD:EE:FF", "my-phone", True),
    _create_device("192.168.178.11", "11:22:33:44:55:66", "my-laptop", True),
    _create_device("192.168.178.12", "22:33:44:55:66:77", "offline-device", False),
]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.arris_tg2492lg.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, title=f"Arris TG2492LG ({MOCK_HOST})"
    )


@pytest.fixture
def mock_connect_box() -> Generator[MagicMock]:
    """Mock ConnectBox to return known connected devices."""
    with (
        patch("homeassistant.components.arris_tg2492lg.coordinator.ConnectBox") as mock,
        patch(
            "homeassistant.components.arris_tg2492lg.config_flow.ConnectBox", new=mock
        ),
    ):
        connect_box = MagicMock()
        connect_box.async_login = AsyncMock(return_value="token")
        connect_box.async_get_connected_devices = AsyncMock(return_value=MOCK_DEVICES)
        mock.return_value = connect_box
        yield mock
