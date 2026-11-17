"""Fixtures for Sky Hub tests."""

from collections.abc import Generator
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sky_hub.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import CONF_HOST


class MockDevice(NamedTuple):
    """A device reported by Sky Hub."""

    mac: str
    name: str


LAPTOP = MockDevice("AA:BB:CC:DD:EE:FF", "Laptop")
PHONE = MockDevice("11:22:33:44:55:66", "Phone")


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock config-entry setup for flow tests."""
    with patch(
        "homeassistant.components.sky_hub.async_setup_entry", return_value=None
    ) as mock:
        yield mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Sky Hub config entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_HOST: DEFAULT_HOST})


@pytest.fixture
def mock_router() -> Generator[MagicMock]:
    """Mock the Sky Hub client."""
    with (
        patch("homeassistant.components.sky_hub.SkyQHub", autospec=True) as client,
        patch("homeassistant.components.sky_hub.coordinator.SkyQHub", new=client),
        patch("homeassistant.components.sky_hub.config_flow.SkyQHub", new=client),
    ):
        router = client.return_value
        router.success_init = True
        router.async_get_skyhub_data.return_value = [LAPTOP]
        yield router
