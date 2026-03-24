"""Fixtures for the luci integration tests."""

from collections.abc import Generator
from typing import NamedTuple
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.luci.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry

MOCK_DEVICE_1 = NamedTuple("Device", ["mac", "hostname", "ip", "reachable", "host"])(
    mac="AA:BB:CC:DD:EE:FF",
    hostname="device1",
    ip="192.168.1.100",
    reachable=True,
    host="192.168.1.1",
)
MOCK_DEVICE_2 = NamedTuple("Device", ["mac", "hostname", "ip", "reachable", "host"])(
    mac="11:22:33:44:55:66",
    hostname="device2",
    ip="192.168.1.101",
    reachable=True,
    host="192.168.1.1",
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "root",
            CONF_PASSWORD: "password",
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
        unique_id=None,
    )


@pytest.fixture
def mock_luci_client() -> Generator[MagicMock]:
    """Return a mock OpenWrtRpc client."""
    with patch(
        "homeassistant.components.luci.coordinator.OpenWrtRpc",
        autospec=True,
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.is_logged_in.return_value = True
        client.get_all_connected_devices.return_value = [MOCK_DEVICE_1, MOCK_DEVICE_2]
        client.router = MagicMock()
        client.router.owrt_version = MagicMock()
        client.router.owrt_version.release = None
        yield client
