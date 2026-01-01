"""Common fixtures for the HDFury tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.hdfury.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

TEST_HOST = "192.168.1.123"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hdfury.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="000123456789",
        data={
            CONF_HOST: TEST_HOST,
        },
    )


@pytest.fixture(autouse=True)
def mock_hdfury_client() -> Generator[AsyncMock]:
    """Mock a HDFury client."""
    with patch(
        "homeassistant.components.hdfury.config_flow.HDFuryAPI",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.get_board = AsyncMock(
            return_value={
                "hostname": "VRROOM-02",
                "ipaddress": "192.168.1.123",
                "serial": "000123456789",
                "pcbv": "3",
                "version": "FW: 0.61",
            }
        )
        yield client
