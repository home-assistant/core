"""Module containing fixtures for testing the WatchYourLAN integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.watchyourlan.const import DOMAIN
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.watchyourlan.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def mock_watchyourlan_client_fixture() -> AsyncMock:
    """Fixture to mock WatchYourLANClient."""
    with patch(
        "homeassistant.components.watchyourlan.config_flow.WatchYourLANClient",
    ) as mock_client:
        instance = mock_client.return_value
        instance.get_all_hosts = AsyncMock(return_value={})
        yield instance


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Fixture for a mock WatchYourLAN config entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://127.0.0.1:8840", CONF_VERIFY_SSL: False},
        title="WatchYourLAN",
        unique_id="http://127.0.0.1:8840",
    )
    mock_entry.add_to_hass(hass)
    return mock_entry


@pytest.fixture
def mock_watchyourlan_hosts():
    """Fixture to provide a mock response for get_all_hosts."""
    return [
        {
            "ID": 1,
            "Name": "Device 1",
            "Iface": "eth0",
            "IP": "192.168.1.100",
            "Mac": "11:22:33:44:55:66",
            "Hw": "Acme, Inc.",
            "Date": "2024-09-01 00:00:00",
            "Known": 1,
            "Now": 1,
        },
        {
            "ID": 2,
            "Name": "Device 2",
            "Iface": "eth1",
            "IP": "192.168.1.101",
            "Mac": "66:55:44:33:22:11",
            "Hw": "Acme, Inc.",
            "Date": "2024-09-01 23:59:59",
            "Known": 1,
            "Now": 0,
        },
    ]
