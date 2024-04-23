"""Fixtures for tests."""

import time
from unittest.mock import AsyncMock, patch

from monzopy.monzopy import UserAccount
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.monzo.api import AuthenticatedMonzoAPI
from homeassistant.components.monzo.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
TEST_ACCOUNTS = [
    {
        "id": "acc_curr",
        "name": "Current Account",
        "type": "uk_retail",
        "balance": {"balance": 123, "total_balance": 321},
    },
    {
        "id": "acc_flex",
        "name": "Flex",
        "type": "uk_monzo_flex",
        "balance": {"balance": 123, "total_balance": 321},
    },
]
TEST_POTS = [
    {
        "id": "pot_savings",
        "name": "Savings",
        "style": "savings",
        "balance": 134578,
        "currency": "GBP",
        "type": "instant_access",
    }
]
TITLE = "jake"
USER_ID = 12345


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET, DOMAIN),
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def polling_config_entry(expires_at: int) -> MockConfigEntry:
    """Create Monzo entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=str(USER_ID),
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "status": 0,
                "userid": str(USER_ID),
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 60,
                "expires_at": time.time() + 1000,
            },
            "profile": TITLE,
        },
    )


@pytest.fixture(name="basic_monzo")
def mock_basic_monzo():
    """Mock monzo with one pot."""

    mock = AsyncMock(spec=AuthenticatedMonzoAPI)
    mock_user_account = AsyncMock(spec=UserAccount)

    mock_user_account.accounts.return_value = []

    mock_user_account.pots.return_value = TEST_POTS

    mock.user_account = mock_user_account

    with patch(
        "homeassistant.components.monzo.AuthenticatedMonzoAPI",
        return_value=mock,
    ):
        yield mock


@pytest.fixture(name="monzo")
def mock_monzo():
    """Mock monzo."""

    mock = AsyncMock(spec=AuthenticatedMonzoAPI)
    mock_user_account = AsyncMock(spec=UserAccount)

    mock_user_account.accounts.return_value = TEST_ACCOUNTS
    mock_user_account.pots.return_value = TEST_POTS

    mock.user_account = mock_user_account

    with patch(
        "homeassistant.components.monzo.AuthenticatedMonzoAPI",
        return_value=mock,
    ):
        yield mock
