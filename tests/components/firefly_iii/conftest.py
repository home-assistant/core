"""Common fixtures for the Firefly III tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyfirefly.models import About, Account, Bill, Budget, Category, Currency
import pytest

from homeassistant.components.firefly_iii.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_value_fixture,
)

MOCK_TEST_CONFIG = {
    CONF_URL: "https://127.0.0.1:8080/",
    CONF_API_KEY: "test_api_key",
    CONF_VERIFY_SSL: True,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.firefly_iii.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_firefly_client() -> Generator[AsyncMock]:
    """Mock Firefly client with dynamic exception injection support."""
    with (
        patch(
            "homeassistant.components.firefly_iii.config_flow.Firefly"
        ) as mock_client,
        patch(
            "homeassistant.components.firefly_iii.coordinator.Firefly", new=mock_client
        ),
    ):
        client = mock_client.return_value

        client.get_about = AsyncMock(
            return_value=About.from_dict(load_json_value_fixture("about.json", DOMAIN))
        )
        client.get_accounts = AsyncMock(
            return_value=[
                Account.from_dict(account)
                for account in load_json_array_fixture("accounts.json", DOMAIN)
            ]
        )
        client.get_categories = AsyncMock(
            return_value=[
                Category.from_dict(category)
                for category in load_json_array_fixture("categories.json", DOMAIN)
            ]
        )
        client.get_category = AsyncMock(
            return_value=Category.from_dict(
                load_json_value_fixture("category.json", DOMAIN)
            )
        )
        client.get_currency_primary = AsyncMock(
            return_value=Currency.from_dict(
                load_json_value_fixture("primary_currency.json", DOMAIN)
            )
        )
        client.get_budgets = AsyncMock(
            return_value=[
                Budget.from_dict(budget)
                for budget in load_json_array_fixture("budgets.json", DOMAIN)
            ]
        )
        client.get_bills = AsyncMock(
            return_value=[
                Bill.from_dict(bill)
                for bill in load_json_array_fixture("bills.json", DOMAIN)
            ]
        )
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Firefly III test",
        data=MOCK_TEST_CONFIG,
        entry_id="firefly_iii_test_entry_123",
        unique_id="firefly_iii_test_unique_id_123",
    )
