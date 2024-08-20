"""Common fixtures for the Monarch Money tests."""

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from homeassistant.components.monarchmoney.const import DOMAIN
from homeassistant.const import CONF_TOKEN

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.monarchmoney.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def mock_config_entry() -> MockConfigEntry:
    """Fixture for mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: "fake_token_of_doom"},
        version=1,
    )


@pytest.fixture
def mock_config_api() -> Generator[AsyncMock]:
    """Mock the MonarchMoney class."""

    account_data: dict[str, Any] = json.loads(load_fixture("get_accounts.json", DOMAIN))
    cashflow_summary: dict[str, Any] = json.loads(
        load_fixture("get_cashflow_summary.json", DOMAIN)
    )

    # monarch_data = MonarchData(
    #     account_data=account_data["accounts"],
    #     cashflow_summary=cashflow_summary["summary"][0]["summary"],
    # )

    with (
        patch(
            "homeassistant.components.monarchmoney.config_flow.MonarchMoney",
            autospec=True,
        ) as mock_class,
        patch("homeassistant.components.monarchmoney.MonarchMoney", new=mock_class),
    ):
        instance = mock_class.return_value
        type(instance).token = PropertyMock(return_value="mocked_token")
        instance.login = AsyncMock(return_value=None)
        instance.multi_factor_authenticate = AsyncMock(return_value=None)
        instance.get_subscription_details = AsyncMock(
            return_value={
                "subscription": {
                    "id": "123456789",
                    "paymentSource": "STRIPE",
                    "referralCode": "go3dpvrdmw",
                    "isOnFreeTrial": False,
                    "hasPremiumEntitlement": True,
                    "__typename": "HouseholdSubscription",
                }
            }
        )
        instance.get_accounts = AsyncMock(return_value=account_data)
        instance.get_cashflow_summary = AsyncMock(return_value=cashflow_summary)
        yield mock_class
