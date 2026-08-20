"""Common fixtures for the RainbowMiner tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from tests.test_util.aiohttp import AiohttpClientMocker

TEST_HOST = "1.1.1.1"
TEST_PORT = 4000
TEST_BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}"

VALID_STATUS = {
    "Pause": False,
    "PauseIAOnly": False,
    "LockMiners": False,
    "IsExclusiveRun": False,
    "IsDonationRun": False,
}

VALID_CURRENT_PROFIT: dict[str, Any] = {
    "AllProfitBTC": 0.001,
    "ProfitBTC": 0.0005,
    "Earnings_Avg": 0.0003,
    "Earnings_1d": 0.0072,
    "AllEarnings_Avg": 0.0004,
    "AllEarnings_1d": 0.0096,
    "Rates": {"USD": 60000.0, "EUR": 55000.0, "LTC": 600.0},
    "PowerPrice": 0.1,
    "Power": 350.0,
    "Uptime": {"AsString": "1.00:00:00", "Seconds": 86400},
    "SysUptime": {"AsString": "2.00:00:00", "Seconds": 172800},
    "RemoteIP": "",
}

VALID_UPTIME = {"AsString": "1.00:00:00", "Seconds": 86400}

VALID_ACTIVE_MINERS: list[dict[str, Any]] = [
    {"Name": "miner1", "Status": 0, "Pool": ["MiningPoolHub"]},
    {"Name": "miner2", "Status": 0, "Pool": ["Ethermine"]},
    {"Name": "miner3", "Status": 1, "Pool": ["Zpool"]},
]

VALID_BALANCES: list[dict[str, Any]] = [
    {
        "Name": "MiningPoolHub",
        "BaseName": "MiningPoolHub",
        "Currency": "ETH",
        "Total": 0.01,
        "Paid": 0.5,
        "Earnings": 0.51,
        "Total_BTC": 0.0001,
        "Paid_BTC": 0.005,
        "Earnings_BTC": 0.0051,
        "Earnings_1h_BTC": 0.00002,
        "Earnings_1d_BTC": 0.0005,
        "Earnings_1w_BTC": 0.003,
    },
    {
        "Name": "Ethermine",
        "BaseName": "Ethermine",
        "Currency": "ETH",
        "Total": 0.02,
        "Paid": 1.0,
        "Earnings": 1.02,
        "Total_BTC": 0.0002,
        "Paid_BTC": 0.01,
        "Earnings_BTC": 0.0102,
        "Earnings_1h_BTC": 0.00004,
        "Earnings_1d_BTC": 0.001,
        "Earnings_1w_BTC": 0.006,
    },
]

VALID_VERSION = {"Version": "5.0.0", "MachineName": "test-rig"}


def mock_rainbowminer_endpoints(
    aioclient_mock: AiohttpClientMocker,
    *,
    status: dict[str, Any] | Exception | None = None,
    current_profit: dict[str, Any] | Exception | None = None,
    uptime: dict[str, Any] | Exception | None = None,
    active_miners: list[dict[str, Any]] | Exception | None = None,
    version: dict[str, Any] | Exception | None = None,
    balances: list[dict[str, Any]] | Exception | None = None,
) -> None:
    """Register canned RainbowMiner API responses."""
    responses: dict[str, dict[str, Any] | list[dict[str, Any]] | Exception] = {}
    if status is not None:
        responses["status"] = status
    if current_profit is not None:
        responses["currentprofit"] = current_profit
    if uptime is not None:
        responses["uptime"] = uptime
    if active_miners is not None:
        responses["activeminers"] = active_miners
    if version is not None:
        responses["version"] = version
    if balances is not None:
        responses["balances?add_btc=true"] = balances
    for path, payload in responses.items():
        if isinstance(payload, Exception):
            aioclient_mock.get(f"{TEST_BASE_URL}/{path}", exc=payload)
        else:
            aioclient_mock.get(f"{TEST_BASE_URL}/{path}", json=payload)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.rainbowminer.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
