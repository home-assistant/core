"""Test the RainbowMiner sensors."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from rainbowminer_api_client import CurrentProfit
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rainbowminer.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import (
    VALID_ACTIVE_MINERS,
    VALID_BALANCES,
    VALID_CURRENT_PROFIT,
    VALID_UPTIME,
)


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor entities are fixated in the snapshot."""
    freezer.move_to("2026-09-13 12:00:00+00:00")
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_always_sensors(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the non-currency sensors."""
    freezer.move_to("2026-09-13 12:00:00+00:00")
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.rainbowminer_active_miners")
    assert state is not None
    assert state.state == str(sum(1 for m in VALID_ACTIVE_MINERS if m.Status == 0))

    state = hass.states.get("sensor.rainbowminer_power")
    assert state is not None
    assert state.state == str(VALID_CURRENT_PROFIT.Power)

    state = hass.states.get("sensor.rainbowminer_uptime")
    assert state is not None
    start = dt_util.parse_datetime(state.state)
    assert start is not None
    assert start == dt_util.utcnow() - timedelta(seconds=VALID_UPTIME.Seconds)
    assert start == datetime.fromisoformat("2026-09-12 12:00:00+00:00")

    assert hass.states.get("sensor.rainbowminer_version") is None


async def test_mbtc_sensors(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the mBTC-denominated sensors."""
    await setup_integration(hass, mock_config_entry)

    earnings_btc_sum = sum(b.Earnings_BTC for b in VALID_BALANCES)
    total_btc_sum = sum(b.Total_BTC for b in VALID_BALANCES)
    earnings_1w_btc_sum = sum(b.Earnings_1w_BTC for b in VALID_BALANCES)
    earnings_1d_btc_sum = sum(b.Earnings_1d_BTC for b in VALID_BALANCES)
    earnings_1h_btc_sum = sum(b.Earnings_1h_BTC for b in VALID_BALANCES)

    state = hass.states.get("sensor.rainbowminer_total_bitcoin_earnings")
    assert state is not None
    assert state.state == str(round(earnings_btc_sum * 1000, 10))

    state = hass.states.get("sensor.rainbowminer_unpaid_bitcoin_balance")
    assert state is not None
    assert state.state == str(round(total_btc_sum * 1000, 10))

    state = hass.states.get("sensor.rainbowminer_estimated_daily_bitcoin_profit")
    assert state is not None
    assert state.state == str(VALID_CURRENT_PROFIT.AllProfitBTC * 1000)

    state = hass.states.get("sensor.rainbowminer_weekly_bitcoin_earnings")
    assert state is not None
    assert state.state == str(round(earnings_1w_btc_sum * 1000, 10))

    state = hass.states.get("sensor.rainbowminer_daily_bitcoin_earnings")
    assert state is not None
    assert state.state == str(round(earnings_1d_btc_sum * 1000, 10))

    state = hass.states.get("sensor.rainbowminer_hourly_bitcoin_earnings")
    assert state is not None
    assert state.state == str(round(earnings_1h_btc_sum * 1000, 10))


async def test_currency_sensors(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the currency-denominated sensors."""
    hass.config.currency = "USD"
    await setup_integration(hass, mock_config_entry)

    rate = float(VALID_CURRENT_PROFIT.Rates["USD"])
    earnings_btc_sum = sum(b.Earnings_BTC for b in VALID_BALANCES)
    total_btc_sum = sum(b.Total_BTC for b in VALID_BALANCES)
    earnings_1w_btc_sum = sum(b.Earnings_1w_BTC for b in VALID_BALANCES)
    earnings_1d_btc_sum = sum(b.Earnings_1d_BTC for b in VALID_BALANCES)
    earnings_1h_btc_sum = sum(b.Earnings_1h_BTC for b in VALID_BALANCES)

    state = hass.states.get("sensor.rainbowminer_total_earnings")
    assert state is not None
    assert state.state == str(round(earnings_btc_sum * rate, 10))

    state = hass.states.get("sensor.rainbowminer_unpaid_balance")
    assert state is not None
    assert state.state == str(round(total_btc_sum * rate, 10))

    state = hass.states.get("sensor.rainbowminer_estimated_daily_profit")
    assert state is not None
    assert state.state == str(round(VALID_CURRENT_PROFIT.AllProfitBTC * rate, 10))

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
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test currency sensors are not created when no HA currency is set."""
    hass.config.currency = None
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.rainbowminer_total_earnings") is None
    assert hass.states.get("sensor.rainbowminer_unpaid_balance") is None
    assert hass.states.get("sensor.rainbowminer_weekly_earnings") is None
    assert hass.states.get("sensor.rainbowminer_daily_earnings") is None
    assert hass.states.get("sensor.rainbowminer_hourly_earnings") is None
    assert hass.states.get("sensor.rainbowminer_estimated_daily_profit") is None


async def test_currency_sensors_unavailable_when_rate_missing(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test currency sensors are unavailable when the currency isn't in Rates."""
    hass.config.currency = "USD"
    mock_rainbowminer_client.get_current_profit.return_value = CurrentProfit(
        AllProfitBTC=VALID_CURRENT_PROFIT.AllProfitBTC,
        Rates={"EUR": 55000.0},
        Power=VALID_CURRENT_PROFIT.Power,
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.rainbowminer_total_earnings")
    assert state is not None
    assert state.state == "unknown"

    state = hass.states.get("sensor.rainbowminer_estimated_daily_profit")
    assert state is not None
    assert state.state == "unknown"


async def test_mbtc_sensors_unavailable_without_balances(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test balance-derived mBTC sensors are unknown when no balances."""
    mock_rainbowminer_client.get_balances.return_value = []
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.rainbowminer_total_bitcoin_earnings")
    assert state is not None
    assert state.state == "unknown"

    state = hass.states.get("sensor.rainbowminer_unpaid_bitcoin_balance")
    assert state is not None
    assert state.state == "unknown"


async def test_device_info(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device registry entry contains the software version."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
