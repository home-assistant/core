"""Fixtures for Ping integration tests."""
from unittest.mock import patch

import pytest

from homeassistant.components.ping import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MockConfigEntry for testing."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "imported_by": "binary_sensor",
            "name": "Router",
            "host": "192.168.178.1",
            "count": 10,
        },
        title="Router",
    )
    config_entry.add_to_hass(hass)

    return config_entry


@pytest.fixture
async def non_imported_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MockConfigEntry for testing."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "Smartphone",
            "host": "192.168.178.10",
            "count": 10,
        },
        title="Smartphone",
    )
    config_entry.add_to_hass(hass)

    return config_entry


@pytest.fixture
def mock_ping() -> None:
    """Mock icmplib.ping."""
    with patch("homeassistant.components.ping.icmp_ping"):
        yield


@pytest.fixture
def mock_async_ping() -> None:
    """Mock icmplib.ping."""
    with patch("homeassistant.components.ping.ping.async_ping"):
        yield
