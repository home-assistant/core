"""Fixtures for Sequence integration tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from GetSequenceIoApiClient import (
    SequenceApiError,
    SequenceAuthError,
    SequenceConnectionError,
)
import pytest

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN

from tests.common import MockConfigEntry

CONF_DATA_USER = {
    CONF_ACCESS_TOKEN: "test_token_12345",
    CONF_NAME: "Sequence Account",
}

CONF_DATA_REAUTH = {
    CONF_ACCESS_TOKEN: "test_token_reauth_67890",
}


def get_account_data(
    account_id: str = "acc_001",
    account_name: str = "Savings Account",
    balance: float = 5000.00,
    balance_error: str | None = None,
) -> dict[str, Any]:
    """Generate mock account data."""
    account = {
        "id": account_id,
        "name": account_name,
        "type": "savings",
        "balance": {
            "amountInDollars": balance,
        },
    }
    if balance_error:
        account["balance"]["displayMessage"] = balance_error
    return account


def get_accounts_response(
    accounts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate mock API response with accounts."""
    if accounts is None:
        accounts = [get_account_data()]
    return {
        "data": {
            "accounts": accounts,
        }
    }


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA_USER,
        title="Sequence Account",
    )


@pytest.fixture
def mock_config_entry_reauth() -> MockConfigEntry:
    """Return a mocked config entry for reauth testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA_USER,
        title="Sequence Account",
    )
    entry.state = "not_loaded"
    return entry


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Return a mocked SequenceApiClient."""
    client = AsyncMock()
    client.async_get_accounts = AsyncMock(return_value=get_accounts_response())
    return client


@pytest.fixture
def mock_api_client_auth_error() -> MagicMock:
    """Return a mocked SequenceApiClient that raises SequenceAuthError."""
    client = AsyncMock()
    client.async_get_accounts = AsyncMock(
        side_effect=SequenceAuthError("Invalid token")
    )
    return client


@pytest.fixture
def mock_api_client_connection_error() -> MagicMock:
    """Return a mocked SequenceApiClient that raises SequenceConnectionError."""
    client = AsyncMock()
    client.async_get_accounts = AsyncMock(
        side_effect=SequenceConnectionError("Network error")
    )
    return client


@pytest.fixture
def mock_api_client_api_error() -> MagicMock:
    """Return a mocked SequenceApiClient that raises SequenceApiError."""
    client = AsyncMock()
    client.async_get_accounts = AsyncMock(side_effect=SequenceApiError("API error"))
    return client


@pytest.fixture
def mock_api_client_empty_accounts() -> MagicMock:
    """Return a mocked SequenceApiClient with empty accounts list."""
    client = AsyncMock()
    client.async_get_accounts = AsyncMock(
        return_value=get_accounts_response(accounts=[])
    )
    return client


@pytest.fixture
def mock_api_client_missing_balance() -> MagicMock:
    """Return a mocked SequenceApiClient with account missing balance."""
    account = {
        "id": "acc_001",
        "name": "Savings Account",
        "type": "savings",
    }
    client = AsyncMock()
    client.async_get_accounts = AsyncMock(
        return_value=get_accounts_response(accounts=[account])
    )
    return client


@pytest.fixture
def mock_api_client_missing_balance_amount() -> MagicMock:
    """Return a mocked SequenceApiClient with account missing amountInDollars."""
    account = {
        "id": "acc_001",
        "name": "Savings Account",
        "type": "savings",
        "balance": {
            "displayMessage": "Balance unavailable",
        },
    }
    client = AsyncMock()
    client.async_get_accounts = AsyncMock(
        return_value=get_accounts_response(accounts=[account])
    )
    return client


@pytest.fixture
def mock_api_client_multiple_accounts() -> MagicMock:
    """Return a mocked SequenceApiClient with multiple accounts."""
    accounts = [
        get_account_data(account_id="acc_001", account_name="Savings"),
        get_account_data(
            account_id="acc_002", account_name="Checking", balance=2500.00
        ),
        get_account_data(
            account_id="acc_003", account_name="Investment", balance=15000.00
        ),
    ]
    client = AsyncMock()
    client.async_get_accounts = AsyncMock(
        return_value=get_accounts_response(accounts=accounts)
    )
    return client


@pytest.fixture
def mock_api_client_with_error_message() -> MagicMock:
    """Return a mocked SequenceApiClient with account balance error message."""
    account = get_account_data(
        balance_error="Unable to fetch balance from upstream service"
    )
    client = AsyncMock()
    client.async_get_accounts = AsyncMock(
        return_value=get_accounts_response(accounts=[account])
    )
    return client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api_client: MagicMock
) -> MockConfigEntry:
    """Initialize the integration."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.coordinator.SequenceApiClient",
        return_value=mock_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
async def init_integration_with_multiple_accounts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client_multiple_accounts: MagicMock,
) -> MockConfigEntry:
    """Initialize the integration with multiple accounts."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.coordinator.SequenceApiClient",
        return_value=mock_api_client_multiple_accounts,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
