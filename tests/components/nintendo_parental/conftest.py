"""Common fixtures for the Nintendo Switch Parental Controls tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.nintendo_parental.const import DOMAIN

from .const import ACCOUNT_ID, API_TOKEN, LOGIN_URL

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"session_token": API_TOKEN},
        unique_id=ACCOUNT_ID,
    )


@pytest.fixture
def mock_nintendo_authenticator() -> Generator[MagicMock]:
    """Mock Nintendo Authenticator."""
    with (
        patch(
            "homeassistant.components.nintendo_parental.Authenticator",
            autospec=True,
        ) as mock_auth_class,
        patch(
            "homeassistant.components.nintendo_parental.config_flow.Authenticator",
            new=mock_auth_class,
        ),
        patch(
            "homeassistant.components.nintendo_parental.coordinator.NintendoParental.update",
            return_value=None,
        ),
    ):
        mock_auth = MagicMock()
        mock_auth._id_token = API_TOKEN
        mock_auth._at_expiry = datetime(2099, 12, 31, 23, 59, 59)
        mock_auth.account_id = ACCOUNT_ID
        mock_auth.login_url = LOGIN_URL
        mock_auth.get_session_token = API_TOKEN
        # Patch complete_login as an AsyncMock on both instance and class as this is a class method
        mock_auth.complete_login = AsyncMock()
        type(mock_auth).complete_login = mock_auth.complete_login
        mock_auth_class.generate_login.return_value = mock_auth
        yield mock_auth


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nintendo_parental.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
