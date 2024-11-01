"""Collection of helpers."""

from homeassistant.components.coinbase.const import (
    CONF_CURRENCIES,
    CONF_EXCHANGE_RATES,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_API_VERSION
from homeassistant.core import HomeAssistant

from .const import (
    GOOD_CURRENCY_2,
    GOOD_EXCHANGE_RATE,
    GOOD_EXCHANGE_RATE_2,
    MOCK_ACCOUNTS_RESPONSE,
    MOCK_ACCOUNTS_RESPONSE_V3,
)

from tests.common import MockConfigEntry


class MockPagination:
    """Mock pagination result."""

    def __init__(self, value=None) -> None:
        """Load simple pagination for tests."""
        self.next_starting_after = value


class MockGetAccounts:
    """Mock accounts with pagination."""

    def __init__(self, starting_after=0) -> None:
        """Init mocked object, forced to return two at a time."""
        if (target_end := starting_after + 2) >= (
            max_end := len(MOCK_ACCOUNTS_RESPONSE)
        ):
            end = max_end
            self.pagination = MockPagination(value=None)
        else:
            end = target_end
            self.pagination = MockPagination(value=target_end)

        self.accounts = {
            "data": MOCK_ACCOUNTS_RESPONSE[starting_after:end],
        }
        self.started_at = starting_after

    def __getitem__(self, item):
        """Handle subscript request."""
        return self.accounts[item]


def mocked_get_accounts(_, **kwargs):
    """Return simplified accounts using mock."""
    return MockGetAccounts(**kwargs)


class MockGetAccountsV3:
    """Mock accounts with pagination."""

    def __init__(self, cursor="") -> None:
        """Init mocked object, forced to return two at a time."""
        ids = [account["uuid"] for account in MOCK_ACCOUNTS_RESPONSE_V3]
        start = ids.index(cursor) if cursor else 0

        has_next = (target_end := start + 2) < len(MOCK_ACCOUNTS_RESPONSE_V3)
        end = target_end if has_next else -1
        next_cursor = ids[end] if has_next else ids[-1]
        self.accounts = {
            "accounts": MOCK_ACCOUNTS_RESPONSE_V3[start:end],
            "has_next": has_next,
            "cursor": next_cursor,
        }

    def __getitem__(self, item):
        """Handle subscript request."""
        return self.accounts[item]


def mocked_get_accounts_v3(_, **kwargs):
    """Return simplified accounts using mock."""
    return MockGetAccountsV3(**kwargs)


def mock_get_current_user():
    """Return a simplified mock user."""
    return {
        "id": "123456-abcdef",
        "name": "Test User",
    }


def mock_get_exchange_rates():
    """Return a heavily reduced mock list of exchange rates for testing."""
    return {
        "currency": "USD",
        "rates": {
            GOOD_CURRENCY_2: "1.0",
            GOOD_EXCHANGE_RATE_2: "0.109",
            GOOD_EXCHANGE_RATE: "0.00002",
        },
    }


def mock_get_portfolios():
    """Return a mocked list of Coinbase portfolios."""
    return {
        "portfolios": [
            {
                "name": "Default",
                "uuid": "123456",
                "type": "DEFAULT",
            }
        ]
    }


async def init_mock_coinbase(
    hass: HomeAssistant,
    currencies: list[str] | None = None,
    rates: list[str] | None = None,
) -> MockConfigEntry:
    """Init Coinbase integration for testing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="080272b77a4f80c41b94d7cdc86fd826",
        unique_id=None,
        title="Test User",
        data={CONF_API_KEY: "123456", CONF_API_TOKEN: "AbCDeF"},
        options={
            CONF_CURRENCIES: currencies or [],
            CONF_EXCHANGE_RATES: rates or [],
        },
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def init_mock_coinbase_v3(
    hass: HomeAssistant,
    currencies: list[str] | None = None,
    rates: list[str] | None = None,
) -> MockConfigEntry:
    """Init Coinbase integration for testing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="080272b77a4f80c41b94d7cdc86fd826",
        unique_id=None,
        title="Test User v3",
        data={
            CONF_API_KEY: "organizations/123456",
            CONF_API_TOKEN: "AbCDeF",
            CONF_API_VERSION: "v3",
        },
        options={
            CONF_CURRENCIES: currencies or [],
            CONF_EXCHANGE_RATES: rates or [],
        },
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
