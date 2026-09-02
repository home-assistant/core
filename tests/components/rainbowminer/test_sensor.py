"""Test the RainbowMiner sensors."""

from typing import Any
from unittest.mock import patch

from homeassistant.components.rainbowminer.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_HOST,
    TEST_PORT,
    VALID_ACTIVE_MINERS,
    VALID_BALANCES,
    VALID_CURRENT_PROFIT,
    VALID_STATUS,
    VALID_UPTIME,
    VALID_VERSION,
    mock_rainbowminer_endpoints,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


def _register_all(
    aioclient_mock: AiohttpClientMocker,
    *,
    current_profit: dict[str, Any] | None = None,
    active_miners: list[dict[str, Any]] | None = None,
    balances: list[dict[str, Any]] | None = None,
) -> None:
    """Register canned responses for all endpoints."""
    mock_rainbowminer_endpoints(
        aioclient_mock,
        status=VALID_STATUS,
        current_profit=current_profit
        if current_profit is not None
        else VALID_CURRENT_PROFIT,
        uptime=VALID_UPTIME,
        active_miners=active_miners
        if active_miners is not None
        else VALID_ACTIVE_MINERS,
        version=VALID_VERSION,
        balances=balances if balances is not None else VALID_BALANCES,
    )


async def _setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    *,
    currency: str | None = "USD",
    current_profit: dict[str, Any] | None = None,
    active_miners: list[dict[str, Any]] | None = None,
    balances: list[dict[str, Any]] | None = None,
) -> None:
    """Set up the integration with the given HA currency."""
    _register_all(
        aioclient_mock,
        current_profit=current_profit,
        active_miners=active_miners,
        balances=balances,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT},
    )
    entry.add_to_hass(hass)
    with patch.object(hass.config, "currency", currency):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_always_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the non-currency sensors."""
    await _setup(hass, aioclient_mock)

    state = hass.states.get("sensor.rainbowminer_active_miners")
    assert state is not None
    assert state.state == str(
        sum(1 for m in VALID_ACTIVE_MINERS if m.get("Status") == 0)
    )

    state = hass.states.get("sensor.rainbowminer_active_pools")
    assert state is not None
    assert state.state == "MiningPoolHub, Ethermine"

    state = hass.states.get("sensor.rainbowminer_power")
    assert state is not None
    assert state.state == str(VALID_CURRENT_PROFIT["Power"])

    state = hass.states.get("sensor.rainbowminer_uptime")
    assert state is not None
    assert state.state == str(VALID_UPTIME["Seconds"])
    assert state.attributes["formatted"] == "1 day"

    state = hass.states.get("sensor.rainbowminer_version")
    assert state is not None
    assert state.state == "5.0.0"


async def test_mbtc_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the mBTC-denominated sensors."""
    await _setup(hass, aioclient_mock)

    earnings_btc_sum = sum(b["Earnings_BTC"] for b in VALID_BALANCES)
    total_btc_sum = sum(b["Total_BTC"] for b in VALID_BALANCES)
    earnings_1w_btc_sum = sum(b["Earnings_1w_BTC"] for b in VALID_BALANCES)
    earnings_1d_btc_sum = sum(b["Earnings_1d_BTC"] for b in VALID_BALANCES)
    earnings_1h_btc_sum = sum(b["Earnings_1h_BTC"] for b in VALID_BALANCES)

    state = hass.states.get("sensor.rainbowminer_total_earnings_mbtc")
    assert state is not None
    assert state.state == str(round(earnings_btc_sum * 1000, 10))

    state = hass.states.get("sensor.rainbowminer_unpaid_balance_mbtc")
    assert state is not None
    assert state.state == str(round(total_btc_sum * 1000, 10))

    state = hass.states.get("sensor.rainbowminer_estimated_daily_profit_mbtc")
    assert state is not None
    assert state.state == str(VALID_CURRENT_PROFIT["AllProfitBTC"] * 1000)

    state = hass.states.get("sensor.rainbowminer_weekly_earnings_mbtc")
    assert state is not None
    assert state.state == str(round(earnings_1w_btc_sum * 1000, 10))

    state = hass.states.get("sensor.rainbowminer_daily_earnings_mbtc")
    assert state is not None
    assert state.state == str(round(earnings_1d_btc_sum * 1000, 10))

    state = hass.states.get("sensor.rainbowminer_hourly_earnings_mbtc")
    assert state is not None
    assert state.state == str(round(earnings_1h_btc_sum * 1000, 10))


async def test_currency_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the currency-denominated sensors."""
    await _setup(hass, aioclient_mock, currency="USD")

    rate = float(VALID_CURRENT_PROFIT["Rates"]["USD"])
    earnings_btc_sum = sum(b["Earnings_BTC"] for b in VALID_BALANCES)
    total_btc_sum = sum(b["Total_BTC"] for b in VALID_BALANCES)
    earnings_1w_btc_sum = sum(b["Earnings_1w_BTC"] for b in VALID_BALANCES)
    earnings_1d_btc_sum = sum(b["Earnings_1d_BTC"] for b in VALID_BALANCES)
    earnings_1h_btc_sum = sum(b["Earnings_1h_BTC"] for b in VALID_BALANCES)
    all_profit_btc = float(VALID_CURRENT_PROFIT["AllProfitBTC"])

    state = hass.states.get("sensor.rainbowminer_total_earnings")
    assert state is not None
    assert state.state == str(round(earnings_btc_sum * rate, 10))

    state = hass.states.get("sensor.rainbowminer_unpaid_balance")
    assert state is not None
    assert state.state == str(round(total_btc_sum * rate, 10))

    state = hass.states.get("sensor.rainbowminer_estimated_daily_profit")
    assert state is not None
    assert state.state == str(round(all_profit_btc * rate, 10))

    state = hass.states.get("sensor.rainbowminer_weekly_earnings")
    assert state is not None
    assert state.state == str(round(earnings_1w_btc_sum * rate, 10))

    state = hass.states.get("sensor.rainbowminer_daily_earnings")
    assert state is not None
    assert state.state == str(round(earnings_1d_btc_sum * rate, 10))

    state = hass.states.get("sensor.rainbowminer_hourly_earnings")
    assert state is not None
    assert state.state == str(round(earnings_1h_btc_sum * rate, 10))


async def test_currency_sensors_not_created_without_currency(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test currency sensors are not created when no HA currency is set."""
    await _setup(hass, aioclient_mock, currency=None)

    assert hass.states.get("sensor.rainbowminer_total_earnings") is None
    assert hass.states.get("sensor.rainbowminer_unpaid_balance") is None
    assert hass.states.get("sensor.rainbowminer_weekly_earnings") is None
    assert hass.states.get("sensor.rainbowminer_daily_earnings") is None
    assert hass.states.get("sensor.rainbowminer_hourly_earnings") is None
    assert hass.states.get("sensor.rainbowminer_estimated_daily_profit") is None


async def test_currency_sensors_unavailable_when_rate_missing(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test currency sensors are unavailable when the currency isn't in Rates."""
    profit = {
        **VALID_CURRENT_PROFIT,
        "Rates": {"EUR": 55000.0},
    }
    await _setup(hass, aioclient_mock, currency="USD", current_profit=profit)

    state = hass.states.get("sensor.rainbowminer_total_earnings")
    assert state is not None
    assert state.state == "unknown"

    state = hass.states.get("sensor.rainbowminer_estimated_daily_profit")
    assert state is not None
    assert state.state == "unknown"


async def test_active_pools_empty(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test active_pools sensor returns unknown when no miners are running."""
    miners = [
        {"Name": "miner1", "Status": 1, "Pool": ["Zpool"]},
    ]
    await _setup(hass, aioclient_mock, active_miners=miners)

    state = hass.states.get("sensor.rainbowminer_active_pools")
    assert state is not None
    assert state.state == "unknown"


async def test_active_pools_deduplicated(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test active_pools sensor deduplicates pool names from running miners."""
    miners = [
        {"Name": "miner1", "Status": 0, "Pool": ["Zpool"]},
        {"Name": "miner2", "Status": 0, "Pool": ["Zpool"]},
        {"Name": "miner3", "Status": 0, "Pool": ["Ethermine"]},
    ]
    await _setup(hass, aioclient_mock, active_miners=miners)

    state = hass.states.get("sensor.rainbowminer_active_pools")
    assert state is not None
    assert state.state == "Zpool, Ethermine"


async def test_active_pools_truncated(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test active_pools sensor truncates to 255 characters."""
    miners = [
        {"Name": f"miner{i}", "Status": 0, "Pool": [f"Pool{i:03d}"]} for i in range(100)
    ]
    await _setup(hass, aioclient_mock, active_miners=miners)

    state = hass.states.get("sensor.rainbowminer_active_pools")
    assert state is not None
    assert len(state.state) <= 255
    assert state.state.endswith("...")


async def test_mbtc_sensors_unavailable_without_balances(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test balance-derived mBTC sensors are unknown when no balances."""
    await _setup(hass, aioclient_mock, balances=[])

    state = hass.states.get("sensor.rainbowminer_total_earnings_mbtc")
    assert state is not None
    assert state.state == "unknown"

    state = hass.states.get("sensor.rainbowminer_unpaid_balance_mbtc")
    assert state is not None
    assert state.state == "unknown"
