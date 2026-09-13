"""Fixtures for the arris_tg2492lg integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from arris_tg2492lg import Device
import pytest

from homeassistant.components.arris_tg2492lg.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from tests.common import MockConfigEntry


def _create_device(
    mac: str | None, hostname: str | None, ip: str, online: bool
) -> Device:
    """Create a Device object as returned by the arris_tg2492lg library."""
    device = Device(ip)
    device.mac = mac
    device.hostname = hostname
    device.online = online
    return device


MOCK_DEVICES: list[Device] = [
    _create_device("AA:BB:CC:DD:EE:FF", "my-phone", "192.168.178.10", True),
    _create_device("11:22:33:44:55:66", "my-laptop", "192.168.178.11", True),
    # Offline device: must not produce an entity.
    _create_device("22:33:44:55:66:77", "my-tablet", "192.168.178.12", False),
    # Dual-stack duplicate of my-phone (IPv6): must be deduplicated.
    _create_device("AA:BB:CC:DD:EE:FF", "my-phone", "2001:db8::10", True),
    # No MAC address: must be skipped.
    _create_device(None, "no-mac", "192.168.178.13", True),
]

LATE_DEVICE = _create_device("33:44:55:66:77:88", "my-desktop", "192.168.178.20", True)


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.arris_tg2492lg.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JBVVVJ87F6G5V0QJX6HBC94T",
        title="192.168.178.1",
        data={
            CONF_HOST: "192.168.178.1",
            CONF_PASSWORD: "password",
        },
    )


@pytest.fixture
def mock_connect_box() -> Generator[MagicMock]:
    """Return a mock ConnectBox router client."""
    with (
        patch(
            "homeassistant.components.arris_tg2492lg.ConnectBox",
            autospec=True,
        ) as mock_connect_box_class,
        patch(
            "homeassistant.components.arris_tg2492lg.config_flow.ConnectBox",
            new=mock_connect_box_class,
        ),
    ):
        connect_box = mock_connect_box_class.return_value
        connect_box.async_get_connected_devices.return_value = MOCK_DEVICES
        yield connect_box
