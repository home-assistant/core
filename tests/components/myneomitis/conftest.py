"""conftest.py for myneomitis integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.myneomitis.const import (
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_pyaxenco_client() -> Generator[AsyncMock]:
    """Mock the PyAxencoAPI client across the integration."""
    with (
        patch("pyaxencoapi.PyAxencoAPI", autospec=True) as mock_client,
        patch(
            "homeassistant.components.myneomitis.config_flow.PyAxencoAPI",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login = AsyncMock()
        client.connect_websocket = AsyncMock()
        client.get_devices = AsyncMock(return_value=[])
        client.disconnect_websocket = AsyncMock()
        client.user_id = "user-123"
        client.token = "tok"
        client.refresh_token = "rtok"

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry for the MyNeoMitis integration."""
    return MockConfigEntry(
        title="MyNeo (test@example.com)",
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "password123",
            CONF_TOKEN: "tok",
            CONF_REFRESH_TOKEN: "rtok",
            CONF_USER_ID: "user-123",
        },
        unique_id="user-123",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent running the real integration setup during tests."""
    with patch(
        "homeassistant.components.myneomitis.async_setup_entry",
        new=AsyncMock(return_value=True),
    ) as mock_setup:
        yield mock_setup
