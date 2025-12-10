"""Fixtures for Gentex HomeLink tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_srp_auth() -> Generator[AsyncMock]:
    """Mock SRP authentication."""
    with patch(
        "homeassistant.components.gentex_homelink.config_flow.SRPAuth"
    ) as mock_srp_auth:
        instance = mock_srp_auth.return_value
        instance.async_get_access_token.return_value = {
            "AuthenticationResult": {
                "AccessToken": "access",
                "RefreshToken": "refresh",
                "TokenType": "bearer",
                "ExpiresIn": 3600,
            }
        }
        yield instance


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setup entry."""
    with patch(
        "homeassistant.components.gentex_homelink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
