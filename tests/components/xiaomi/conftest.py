"""Fixtures for the xiaomi integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.xiaomi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


def _create_device(mac: str | None, name: str, online: int, ip: str) -> dict[str, Any]:
    """Create a device entry as returned by the Xiaomi router API."""
    device: dict[str, Any] = {"name": name, "online": online, "ip": [{"ip": ip}]}
    if mac is not None:
        device["mac"] = mac
    return device


MOCK_DEVICE_LIST: list[dict[str, Any]] = [
    _create_device("AA:BB:CC:DD:EE:FF", "my-phone", 1, "192.168.31.10"),
    _create_device("11:22:33:44:55:66", "my-laptop", 1, "192.168.31.11"),
    # Offline device: must not produce an entity.
    _create_device("22:33:44:55:66:77", "my-tablet", 0, "192.168.31.12"),
    # Dual-stack duplicate of my-phone (IPv6): must be deduplicated.
    _create_device("AA:BB:CC:DD:EE:FF", "my-phone", 1, "2001:db8::10"),
    # No MAC address: must be skipped.
    _create_device(None, "no-mac", 1, "192.168.31.13"),
    # Empty MAC address: must be skipped.
    _create_device("", "empty-mac", 1, "192.168.31.14"),
]

LATE_DEVICE = _create_device("33:44:55:66:77:88", "my-desktop", 1, "192.168.31.20")


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.xiaomi.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JBVVVJ87F6G5V0QJX6HBC94T",
        title="192.168.31.1",
        data={
            CONF_HOST: "192.168.31.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )


@pytest.fixture
def mock_xiaomi_client() -> Generator[MagicMock]:
    """Return a mock XiaomiClient router client."""
    with (
        patch(
            "homeassistant.components.xiaomi.XiaomiClient",
        ) as mock_xiaomi_client_class,
        patch(
            "homeassistant.components.xiaomi.config_flow.XiaomiClient",
            new=mock_xiaomi_client_class,
        ),
    ):
        xiaomi_client = mock_xiaomi_client_class.return_value
        xiaomi_client.get_device_list.return_value = MOCK_DEVICE_LIST
        yield xiaomi_client
