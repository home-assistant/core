"""Fixtures for Xthings Cloud tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.xthings_cloud.const import (
    CONF_EMAIL,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
    DOMAIN,
)

from .const import MOCK_EMAIL, MOCK_REFRESH_TOKEN, MOCK_TOKEN, MOCK_USER_ID

from tests.common import MockConfigEntry


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
        unique_id=MOCK_USER_ID,
    )


@pytest.fixture
def mock_login_success() -> dict:
    """Return successful login response."""
    return {
        "token": MOCK_TOKEN,
        "refresh_token": MOCK_REFRESH_TOKEN,
        "user_id": MOCK_USER_ID,
        "client_id": "mock_client_id",
    }


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
