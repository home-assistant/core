"""Common fixtures for the Monarch Money tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch, PropertyMock

import pytest

from homeassistant.const import CONF_TOKEN
from tests.common import MockConfigEntry
from homeassistant.components.monarchmoney.const import DOMAIN

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
def mock_api() -> Generator[AsyncMock]:
    """Mock the MonarchMoney class."""
    with patch("homeassistant.components.monarchmoney.config_flow.MonarchMoney", autospec=True) as mock_class:
        instance = mock_class.return_value
        type(instance).token = PropertyMock(return_value="mocked_token")
        instance.login = AsyncMock(return_value=None)
        instance.get_subscription_details = AsyncMock(return_value={
            'subscription': {
                'id': '123456789',
                'paymentSource': 'STRIPE',
                'referralCode': 'go3dpvrdmw',
                'isOnFreeTrial': False,
                'hasPremiumEntitlement': True,
                '__typename': 'HouseholdSubscription'
            }
        })
        yield mock_class