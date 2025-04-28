"""Common fixtures for the Monarch Money tests."""

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from typedmonarchmoney.models import (
    MonarchAccount,
    MonarchCashflowSummary,
    MonarchSubscription,
)

from homeassistant.components.monarch_money.const import DOMAIN
from homeassistant.const import CONF_TOKEN

from tests.common import MockConfigEntry, load_fixture, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.monarch_money.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def mock_config_entry() -> MockConfigEntry:
    """Fixture for mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: "fake_token_of_doom"},
        unique_id="222260252323873333",
        version=1,
    )


@pytest.fixture
def mock_config_api() -> Generator[AsyncMock]:
    """Mock the MonarchMoney class."""

    account_json: dict[str, Any] = load_json_object_fixture("get_accounts.json", DOMAIN)
    account_data = [MonarchAccount(data) for data in account_json["accounts"]]
    account_data_dict: dict[str, MonarchAccount] = {
        acc["id"]: MonarchAccount(acc) for acc in account_json["accounts"]
    }

    cashflow_json: dict[str, Any] = json.loads(
        load_fixture("get_cashflow_summary.json", DOMAIN)
    )
    cashflow_summary = MonarchCashflowSummary(cashflow_json)
    subscription_details = MonarchSubscription(
        json.loads(load_fixture("get_subscription_details.json", DOMAIN))
    )

    with (
        patch(
            "homeassistant.components.monarch_money.config_flow.TypedMonarchMoney",
            autospec=True,
        ) as mock_class,
        patch(
            "homeassistant.components.monarch_money.TypedMonarchMoney", new=mock_class
        ),
    ):
        instance = mock_class.return_value
        type(instance).token = PropertyMock(return_value="mocked_token")
        instance.login = AsyncMock(return_value=None)
        instance.multi_factor_authenticate = AsyncMock(return_value=None)
        instance.get_subscription_details = AsyncMock(return_value=subscription_details)
        instance.get_accounts = AsyncMock(return_value=account_data)
        instance.get_accounts_as_dict_with_id_key = AsyncMock(
            return_value=account_data_dict
        )
        instance.get_cashflow_summary = AsyncMock(return_value=cashflow_summary)
        instance.get_subscription_details = AsyncMock(return_value=subscription_details)
        yield mock_class
