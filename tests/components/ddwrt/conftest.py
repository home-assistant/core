"""Fixtures for DD-WRT integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.ddwrt.const import CONF_WIRELESS_ONLY, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.1"
MOCK_USERNAME = "admin"
MOCK_PASSWORD = "password"

MOCK_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
    CONF_WIRELESS_ONLY: True,
}

MOCK_CLIENTS = {
    "AA:BB:CC:DD:EE:FF": {"hostname": "my-phone", "ip": "192.168.1.100"},
    "11:22:33:44:55:66": {"hostname": "my-laptop", "ip": "192.168.1.101"},
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ddwrt.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, title=f"DD-WRT ({MOCK_HOST})"
    )


@pytest.fixture
def mock_router() -> Generator[MagicMock]:
    """Mock DdWrtRouter to return known clients."""
    with (
        patch("homeassistant.components.ddwrt.coordinator.DdWrtRouter") as mock,
        patch("homeassistant.components.ddwrt.config_flow.DdWrtRouter", new=mock),
    ):
        instance = MagicMock()
        instance.get_clients.return_value = MOCK_CLIENTS
        mock.return_value = instance
        yield mock
