"""Constants for testing the Coinbase integration."""

GOOD_CURRENCY = "BTC"
GOOD_CURRENCY_2 = "USD"
GOOD_CURRENCY_3 = "EUR"
GOOD_EXCHNAGE_RATE = "BTC"
GOOD_EXCHNAGE_RATE_2 = "ATOM"
BAD_CURRENCY = "ETH"
BAD_EXCHANGE_RATE = "ETH"

MOCK_ACCOUNTS_RESPONSE = [
    {
        "balance": {"amount": "0.00001", "currency": GOOD_CURRENCY},
        "currency": GOOD_CURRENCY,
        "id": "123456789",
        "name": "BTC Wallet",
        "native_balance": {"amount": "100.12", "currency": GOOD_CURRENCY_2},
    },
    {
        "balance": {"amount": "9.90", "currency": GOOD_CURRENCY_2},
        "currency": "USD",
        "id": "987654321",
        "name": "USD Wallet",
        "native_balance": {"amount": "9.90", "currency": GOOD_CURRENCY_2},
    },
]
