"""Fixtures for the TrueNAS integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.truenas_ce.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL

from .const import NETWORK_INTERFACES, SYSTEM_ID, SYSTEM_INFO, SYSTEM_STATS


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.truenas_ce.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_truenas_client() -> Generator[MagicMock]:
    """Mock the TrueNAS client class."""
    with (
        patch(
            "homeassistant.components.truenas_ce.TrueNASClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.truenas_ce.config_flow.TrueNASClient",
            new=mock_client,
        ),
    ):
        yield mock_client


@pytest.fixture
def mock_truenas_system() -> Generator[AsyncMock]:
    """Mock the TrueNAS system reader."""
    with (
        patch(
            "homeassistant.components.truenas_ce.coordinator.TrueNASSystem",
            autospec=True,
        ) as mock_system_class,
        patch(
            "homeassistant.components.truenas_ce.config_flow.TrueNASSystem",
            new=mock_system_class,
        ),
    ):
        system = mock_system_class.return_value
        system.get_system_id.return_value = SYSTEM_ID
        system.get_system_info.return_value = SYSTEM_INFO
        system.get_network_interfaces.return_value = dict(NETWORK_INTERFACES)
        system.get_system_stats.return_value = SYSTEM_STATS
        yield system


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a TrueNAS config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="truenas",
        unique_id=SYSTEM_ID,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_API_KEY: "1-abcdef",
            CONF_VERIFY_SSL: False,
        },
    )
