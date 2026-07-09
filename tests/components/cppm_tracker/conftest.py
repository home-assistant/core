"""Fixtures for the Aruba ClearPass (cppm_tracker) integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.cppm_tracker.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_ID, CONF_HOST

from tests.common import MockConfigEntry

MOCK_HOST = "clearpass.example.com"

MOCK_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_CLIENT_ID: "client",
    CONF_API_KEY: "secret",
}

MAC_PHONE = "AA:BB:CC:DD:EE:FF"
MAC_LAPTOP = "11:22:33:44:55:66"
MAC_OFFLINE = "99:88:77:66:55:44"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.cppm_tracker.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)


@pytest.fixture
def mock_clearpass() -> Generator[MagicMock]:
    """Mock the ClearPass client with the raw ClearPass API responses."""
    with (
        patch(
            "homeassistant.components.cppm_tracker.coordinator.ClearPass",
            autospec=True,
        ) as mock,
        patch("homeassistant.components.cppm_tracker.config_flow.ClearPass", new=mock),
    ):
        instance = mock.return_value
        instance.access_token = "token"
        instance.get_endpoints.return_value = {
            "_embedded": {
                "items": [
                    {"mac_address": MAC_PHONE},
                    {"mac_address": MAC_LAPTOP},
                    {"mac_address": MAC_OFFLINE},
                ]
            }
        }
        instance.online_status.side_effect = lambda mac: mac != MAC_OFFLINE
        yield mock
