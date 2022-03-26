"""Constants for testing the Coinbase integration."""

from homeassistant.components.diagnostics.const import REDACTED

GOOD_CURRENCY = "BTC"
GOOD_CURRENCY_2 = "USD"
GOOD_CURRENCY_3 = "EUR"
GOOD_EXCHANGE_RATE = "BTC"
GOOD_EXCHANGE_RATE_2 = "ATOM"
BAD_CURRENCY = "ETH"
BAD_EXCHANGE_RATE = "ETH"

MOCK_ACCOUNTS_RESPONSE = [
    {
        "balance": {"amount": "0.00001", "currency": GOOD_CURRENCY},
        "currency": GOOD_CURRENCY,
        "id": "123456789",
        "name": "BTC Wallet",
        "native_balance": {"amount": "100.12", "currency": GOOD_CURRENCY_2},
        "type": "wallet",
    },
    {
        "balance": {"amount": "100.00", "currency": GOOD_CURRENCY},
        "currency": GOOD_CURRENCY,
        "id": "abcdefg",
        "name": "BTC Vault",
        "native_balance": {"amount": "100.12", "currency": GOOD_CURRENCY_2},
        "type": "vault",
    },
    {
        "balance": {"amount": "9.90", "currency": GOOD_CURRENCY_2},
        "currency": "USD",
        "id": "987654321",
        "name": "USD Wallet",
        "native_balance": {"amount": "9.90", "currency": GOOD_CURRENCY_2},
        "type": "fiat",
    },
]

MOCK_ACCOUNTS_RESPONSE_REDACTED = [
    {
        "balance": {"amount": REDACTED, "currency": GOOD_CURRENCY},
        "currency": GOOD_CURRENCY,
        "id": REDACTED,
        "name": "BTC Wallet",
        "native_balance": {"amount": REDACTED, "currency": GOOD_CURRENCY_2},
        "type": "wallet",
    },
    {
        "balance": {"amount": REDACTED, "currency": GOOD_CURRENCY},
        "currency": GOOD_CURRENCY,
        "id": REDACTED,
        "name": "BTC Vault",
        "native_balance": {"amount": REDACTED, "currency": GOOD_CURRENCY_2},
        "type": "vault",
    },
    {
        "balance": {"amount": REDACTED, "currency": GOOD_CURRENCY_2},
        "currency": "USD",
        "id": REDACTED,
        "name": "USD Wallet",
        "native_balance": {"amount": REDACTED, "currency": GOOD_CURRENCY_2},
        "type": "fiat",
    },
]

MOCK_ENTRY_REDACTED = {
    "version": 1,
    "domain": "coinbase",
    "title": REDACTED,
    "data": {"api_token": REDACTED, "api_key": REDACTED},
    "options": {"account_balance_currencies": [], "exchange_rate_currencies": []},
    "pref_disable_new_entities": False,
    "pref_disable_polling": False,
    "source": "user",
    "unique_id": None,
    "disabled_by": None,
}
