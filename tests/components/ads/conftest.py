"""Common fixtures for the ADS tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.ads.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT

from tests.common import MockConfigEntry

AMS_NET_ID = "192.168.1.10.1.1"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ads.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_pyads_connection() -> Generator[MagicMock]:
    """Mock the pyads connection."""
    with patch("pyads.Connection", autospec=True) as mock_connection:
        yield mock_connection.return_value


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=AMS_NET_ID,
        data={
            CONF_DEVICE: AMS_NET_ID,
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_PORT: 851,
        },
    )
