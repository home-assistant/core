"""Constants for testing the Coinbase integration."""

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
        "currency": {"code": GOOD_CURRENCY},
        "id": "123456789",
        "name": "BTC Wallet",
        "type": "wallet",
    },
    {
        "balance": {"amount": "100.00", "currency": GOOD_CURRENCY},
        "currency": {"code": GOOD_CURRENCY},
        "id": "abcdefg",
        "name": "BTC Vault",
        "type": "vault",
    },
    {
        "balance": {"amount": "9.90", "currency": GOOD_CURRENCY_2},
        "currency": {"code": GOOD_CURRENCY_2},
        "id": "987654321",
        "name": "USD Wallet",
        "type": "fiat",
    },
]

MOCK_ACCOUNTS_RESPONSE_V3 = [
    {
        "uuid": "123456789",
        "name": "BTC Wallet",
        "currency": GOOD_CURRENCY,
        "available_balance": {"value": "0.00001", "currency": GOOD_CURRENCY},
        "type": "ACCOUNT_TYPE_CRYPTO",
        "hold": {"value": "0", "currency": GOOD_CURRENCY},
    },
    {
        "uuid": "abcdefg",
        "name": "BTC Vault",
        "currency": GOOD_CURRENCY,
        "available_balance": {"value": "100.00", "currency": GOOD_CURRENCY},
        "type": "ACCOUNT_TYPE_VAULT",
        "hold": {"value": "0", "currency": GOOD_CURRENCY},
    },
    {
        "uuid": "987654321",
        "name": "USD Wallet",
        "currency": GOOD_CURRENCY_2,
        "available_balance": {"value": "9.90", "currency": GOOD_CURRENCY_2},
        "type": "ACCOUNT_TYPE_FIAT",
        "ready": True,
        "hold": {"value": "0", "currency": GOOD_CURRENCY_2},
    },
]
