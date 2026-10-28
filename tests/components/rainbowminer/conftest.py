"""Common fixtures for the RainbowMiner tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from rainbowminer_api_client import (
    ActiveMiner,
    Balance,
    CurrentProfit,
    Status,
    Uptime,
    Version,
)

from homeassistant.components.rainbowminer.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

TEST_HOST = "1.1.1.1"
TEST_PORT = 4000

VALID_STATUS = Status(
    Pause=False,
    PauseIAOnly=False,
    LockMiners=False,
    IsExclusiveRun=False,
    IsDonationRun=False,
)

VALID_CURRENT_PROFIT = CurrentProfit(
    AllProfitBTC=0.001,
    ProfitBTC=0.0005,
    Earnings_Avg=0.0003,
    Earnings_1d=0.0072,
    AllEarnings_Avg=0.0004,
    AllEarnings_1d=0.0096,
    Rates={"USD": 60000.0, "EUR": 55000.0, "LTC": 600.0},
    PowerPrice=0.1,
    Power=350.0,
    Uptime={"AsString": "1.00:00:00", "Seconds": 86400},
    SysUptime={"AsString": "2.00:00:00", "Seconds": 172800},
    RemoteIP="",
)

VALID_UPTIME = Uptime(AsString="1.00:00:00", Seconds=86400)

VALID_ACTIVE_MINERS: list[ActiveMiner] = [
    ActiveMiner(Name="miner1", Status=0, Pool=["MiningPoolHub"]),
    ActiveMiner(Name="miner2", Status=0, Pool=["Ethermine"]),
    ActiveMiner(Name="miner3", Status=1, Pool=["Zpool"]),
]

VALID_BALANCES: list[Balance] = [
    Balance(
        Name="MiningPoolHub",
        BaseName="MiningPoolHub",
        Currency="ETH",
        Total=0.01,
        Paid=0.5,
        Earnings=0.51,
        Total_BTC=0.0001,
        Paid_BTC=0.005,
        Earnings_BTC=0.0051,
        Earnings_1h_BTC=0.00002,
        Earnings_1d_BTC=0.0005,
        Earnings_1w_BTC=0.003,
    ),
    Balance(
        Name="Ethermine",
        BaseName="Ethermine",
        Currency="ETH",
        Total=0.02,
        Paid=1.0,
        Earnings=1.02,
        Total_BTC=0.0002,
        Paid_BTC=0.01,
        Earnings_BTC=0.0102,
        Earnings_1h_BTC=0.00004,
        Earnings_1d_BTC=0.001,
        Earnings_1w_BTC=0.006,
    ),
]

VALID_VERSION = Version(Version="5.0.0")


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.rainbowminer.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_rainbowminer_client() -> Generator[AsyncMock]:
    """Mock a RainbowMiner client."""
    with (
        patch(
            "homeassistant.components.rainbowminer.RainbowMinerClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.rainbowminer.config_flow.RainbowMinerClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_status.return_value = VALID_STATUS
        client.get_current_profit.return_value = VALID_CURRENT_PROFIT
        client.get_uptime.return_value = VALID_UPTIME
        client.get_active_miners.return_value = VALID_ACTIVE_MINERS
        client.get_version.return_value = VALID_VERSION
        client.get_balances.return_value = VALID_BALANCES
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"RainbowMiner {TEST_HOST}:{TEST_PORT}",
        data={CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT},
        entry_id="01M5SW4FE9FGMV9V1T31ZE095V",
    )
