"""Fixtures for Xthings Cloud tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.xthings_cloud.const import (
    CONF_EMAIL,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
    DOMAIN,
)

from tests.common import MockConfigEntry

MOCK_EMAIL = "test@example.com"
MOCK_PASSWORD = "testpassword"
MOCK_TOKEN = "mock_token_123"
MOCK_REFRESH_TOKEN = "mock_refresh_token_456"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_EMAIL,
        data={
            CONF_EMAIL: MOCK_EMAIL,
            CONF_TOKEN: MOCK_TOKEN,
            CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
        },
        unique_id=MOCK_EMAIL,
    )


@pytest.fixture
def mock_login_success() -> dict:
    """Return successful login response."""
    return {
        "token": MOCK_TOKEN,
        "refresh_token": MOCK_REFRESH_TOKEN,
        "client_id": "mock_client_id",
    }


@pytest.fixture
def mock_login_2fa_email() -> dict:
    """Return 2FA email response."""
    return {"2fa": 1}


@pytest.fixture
def mock_login_2fa_phone() -> dict:
    """Return 2FA phone response."""
    return {"2fa": 2}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.xthings_cloud.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_api_client(mock_login_success: dict) -> Generator[AsyncMock]:
    """Mock the XthingsCloudApiClient."""
    with patch(
        "homeassistant.components.xthings_cloud.config_flow.XthingsCloudApiClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.async_login = AsyncMock(return_value=mock_login_success)
        yield client


@pytest.fixture
def mock_instance_id() -> Generator[AsyncMock]:
    """Mock the instance ID."""
    with patch(
        "homeassistant.components.xthings_cloud.config_flow.async_get_instance_id",
        return_value="mock_instance_id",
    ):
        yield
