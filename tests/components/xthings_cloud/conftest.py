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

MOCK_EMAIL = "appdev@u-tec.com"
MOCK_PASSWORD = "Welcome@2022"
MOCK_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhcHBfaWQiOiIxMmE0MmNhZjdkYmI0N2JiYTAxNjM1YzQ4YzQ0YWU1ZiIsInZlcnNpb24iOiIxLjAuMCIsImF1ZCI6Inh0aGluZ3MtNWVhOTlkYTktODIxZC1kYWEyLWNiYjQtNWY2ZjZlM2U1MWRkIiwidXNlcl91dWlkIjoiMDJjN2JhZGYyYjNkNDRkOTUzYjQ4YjU3OWViOWVlYjUiLCJpc3MiOiJjbG91ZC51LXRlYy5jb20iLCJpYXQiOjE3NzY2NTM1MzQsIm5iZiI6MTc3NjY1MzUyNCwiZXhwIjoxNzc3MjU4MzM0fQ.5MU6NiatOOHbX_4Qw2Br4anLi4aPxtvWxML38MgqB9w"
MOCK_REFRESH_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX3V1aWQiOiIwMmM3YmFkZjJiM2Q0NGQ5NTNiNDhiNTc5ZWI5ZWViNSIsImlzcyI6ImNsb3VkLnUtdGVjLmNvbSIsImlhdCI6MTc3NjY1MzUzNCwibmJmIjoxNzc2NjUzNTI0LCJleHAiOjE3NzkyNDU1MzR9.14qnBK9_dUIOaWzWvtewApO1qk3QJiHxOtc-CObT3IM"
MOCK_USER_ID = "02c7badf2b3d44d953b48b579eb9eeb5"


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
