"""Test helpers."""

import pytest

from tests.async_mock import Mock, patch


@pytest.fixture(autouse=True)
def mock_markets():
    """Mock bittrex markets."""
    with patch(
        "aiobittrexapi.Bittrex.get_markets",
        return_value=[
            Mock(
                symbol="ZRX-USD",
                baseCurrencySymbol="ZRX",
                quoteCurrencySymbol="USD",
                minTradeSize="8.00000000",
                precision=5,
                status="ONLINE",
                createdAt="2018-12-11T18:00:07.2Z",
            ),
            Mock(
                symbol="ZRX-USDT",
                baseCurrencySymbol="ZRX",
                quoteCurrencySymbol="USDT",
                minTradeSize="8.00000000",
                precision=8,
                status="ONLINE",
                createdAt="2018-10-17T18:43:03.213Z",
            ),
        ],
    ) as mock_get_markets:
        yield mock_get_markets
