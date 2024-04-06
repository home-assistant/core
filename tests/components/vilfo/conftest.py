"""Vilfo tests conftest."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.vilfo import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.vilfo.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_vilfo_client() -> Generator[AsyncMock, None, None]:
    """Mock a Vilfo client."""
    with patch(
        "homeassistant.components.vilfo.config_flow.VilfoClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.get_board_information.return_value = None
        client.ping.return_value = None
        client.resolve_firmware_version.return_value = "1.1.0"
        client.resolve_mac_address.return_value = "FF-00-00-00-00-00"
        client.mac = "FF-00-00-00-00-00"
        yield client


@pytest.fixture
def mock_is_valid_host() -> Generator[AsyncMock, None, None]:
    """Mock is_valid_host."""
    with patch(
        "homeassistant.components.vilfo.config_flow.is_host_valid",
        return_value=True,
    ) as mock_is_valid_host:
        yield mock_is_valid_host


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="testadmin.vilfo.com",
        unique_id="FF-00-00-00-00-00",
        data={
            CONF_HOST: "testadmin.vilfo.com",
            CONF_ACCESS_TOKEN: "test-token",
        },
    )
