"""Common fixtures for the Sky Hub integration tests."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sky_hub.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.254"

MOCK_CONFIG = {CONF_HOST: MOCK_HOST}

MOCK_DEVICES = [
    SimpleNamespace(mac="AA:BB:CC:DD:EE:FF", name="my-phone"),
    SimpleNamespace(mac="11:22:33:44:55:66", name="my-laptop"),
]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sky_hub.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)


@pytest.fixture
def mock_skyqhub() -> Generator[MagicMock]:
    """Mock SkyQHub to return known devices."""
    with (
        patch("homeassistant.components.sky_hub.coordinator.SkyQHub") as mock,
        patch("homeassistant.components.sky_hub.config_flow.SkyQHub", new=mock),
    ):
        mock.return_value.async_get_skyhub_data = AsyncMock(return_value=MOCK_DEVICES)
        yield mock
