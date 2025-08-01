"""Common fixtures for the Cync by GE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, create_autospec, patch

import pycync
import pytest

MOCKED_USER = pycync.User(
    "test_token",
    "test_refresh_token",
    "test_authorize_string",
    123456789,
    expires_at=3600,
)


@pytest.fixture(autouse=True)
def client():
    """Mock a pycync.Auth client."""
    client_mock = create_autospec(pycync.Auth, instance=True)
    client_mock.user = MOCKED_USER
    client_mock.login = AsyncMock()

    with patch("homeassistant.components.cync_by_ge.config_flow.Auth") as sc_class_mock:
        sc_class_mock.return_value = client_mock
        yield client_mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.cync_by_ge.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
