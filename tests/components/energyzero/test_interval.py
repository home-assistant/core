"""Test electricity resolution with timezone-aware price data."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from energyzero import EnergyPrices, EnergyZeroNoDataError, Interval, PriceType
from energyzero.models import TimeRange
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.energyzero.const import CONF_ELECTRICITY_PRICE_INTERVAL
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("selected", "minutes", "interval"),
    [("hourly", 60, Interval.HOUR), ("quarter_hourly", 15, Interval.QUARTER)],
)
@pytest.mark.parametrize("missing_tomorrow", [False, True])
@pytest.mark.parametrize(
    ("hours", "requests_tomorrow"),
    [
        pytest.param(
            24, True, marks=pytest.mark.freeze_time("2026-04-10 20:32:59"), id="normal"
        ),
        pytest.param(
            23, False, marks=pytest.mark.freeze_time("2026-03-29 00:55:00"), id="spring"
        ),
        pytest.param(
            25, False, marks=pytest.mark.freeze_time("2026-10-25 00:55:00"), id="autumn"
        ),
    ],
)
async def test_electricity_interval(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_energyzero: MagicMock,
    entity_registry: er.EntityRegistry,
    selected: str,
    minutes: int,
    interval: Interval,
    missing_tomorrow: bool,
    hours: int,
    requests_tomorrow: bool,
) -> None:
    """Keep all periods on DST days and use the selected next-price step."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    today = dt_util.now().date()
    start = datetime.combine(
        today, datetime.min.time(), ZoneInfo("Europe/Amsterdam")
    ).astimezone(UTC)
    step = timedelta(minutes=minutes)
    prices = EnergyPrices(
        prices={
            TimeRange(start + index * step, start + (index + 1) * step): float(
                index + 1
            )
            for index in range(hours * 60 // minutes)
        },
        average_price=(hours * 60 // minutes + 1) / 2,
    )
    all_in_prices = EnergyPrices(
        prices={period: price + 100 for period, price in prices.prices.items()},
        average_price=prices.average_price + 100,
    )
    electricity = {
        PriceType.MARKET_WITH_VAT: prices,
        PriceType.ALL_IN: all_in_prices,
    }
    mock_energyzero.get_electricity_prices.side_effect = [
        electricity,
        EnergyZeroNoDataError() if missing_tomorrow else electricity,
    ]
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ELECTRICITY_PRICE_INTERVAL: selected}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    expected = prices.price_at_time(dt_util.utcnow() + step)
    assert expected != prices.current_price
    assert (state := hass.states.get("sensor.energyzero_today_energy_next_hour_price"))
    assert state.state == str(expected)
    assert (
        all_in_state := hass.states.get(
            "sensor.energyzero_today_energy_all_in_next_price"
        )
    )
    assert all_in_state.state == str(expected + 100)
    for suffix, market_value, all_in_value in (
        ("current_hour_price", prices.current_price, all_in_prices.current_price),
        ("average_price", prices.average_price, all_in_prices.average_price),
        ("min_price", prices.extreme_prices[0], all_in_prices.extreme_prices[0]),
        ("max_price", prices.extreme_prices[1], all_in_prices.extreme_prices[1]),
    ):
        assert (state := hass.states.get(f"sensor.energyzero_today_energy_{suffix}"))
        assert state.state == str(market_value)
        all_in_suffix = suffix.replace("current_hour", "current")
        assert (
            state := hass.states.get(
                f"sensor.energyzero_today_energy_all_in_{all_in_suffix}"
            )
        )
        assert state.state == str(all_in_value)
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert diagnostics["electricity_market"]["next_price"] == expected
    assert diagnostics["electricity_market"]["current_price"] == prices.current_price
    assert diagnostics["electricity_market"]["average_price"] == prices.average_price
    assert (
        diagnostics["electricity_market"]["periods_priced_equal_or_lower"]
        == prices.time_ranges_priced_equal_or_lower
    )
    assert diagnostics["electricity_all_in"]["next_price"] == expected + 100
    assert (
        diagnostics["electricity_all_in"]["current_price"]
        == all_in_prices.current_price
    )
    assert (
        diagnostics["electricity_all_in"]["average_price"]
        == all_in_prices.average_price
    )
    assert (
        diagnostics["electricity_all_in"]["min_price"]
        == all_in_prices.extreme_prices[0]
    )
    assert (
        diagnostics["electricity_all_in"]["max_price"]
        == all_in_prices.extreme_prices[1]
    )
    assert all(
        request.kwargs["interval"] == interval
        for request in mock_energyzero.get_electricity_prices.await_args_list
    )
    assert mock_energyzero.get_electricity_prices.await_count == 1 + requests_tomorrow
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 16
    assert all(
        entry.unique_id == f"12345_{entry.entity_id.removeprefix('sensor.energyzero_')}"
        for entry in entries
    )


@pytest.mark.freeze_time("2026-04-10 21:42:00")
@pytest.mark.parametrize(
    ("selected", "minutes"), [("hourly", 60), ("quarter_hourly", 15)]
)
@pytest.mark.parametrize("missing_tomorrow", [False, True])
async def test_next_price_across_midnight(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_energyzero: MagicMock,
    freezer: FrozenDateTimeFactory,
    selected: str,
    minutes: int,
    missing_tomorrow: bool,
) -> None:
    """Use tomorrow prices until the first scheduled refresh after midnight."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    start = dt_util.start_of_local_day().astimezone(UTC)
    step = timedelta(minutes=minutes)
    today_prices = EnergyPrices(
        prices={TimeRange(start, start + timedelta(days=1)): -0.1},
        average_price=-0.1,
    )
    tomorrow_start = start + timedelta(days=1)
    tomorrow_prices = EnergyPrices(
        prices={
            TimeRange(
                tomorrow_start + index * step, tomorrow_start + (index + 1) * step
            ): index / 100
            for index in range(24 * 60 // minutes)
        },
        average_price=0.1,
    )
    all_in_tomorrow = EnergyPrices(
        prices={
            period: price + 0.11 for period, price in tomorrow_prices.prices.items()
        },
        average_price=0.21,
    )
    today = {PriceType.MARKET_WITH_VAT: today_prices, PriceType.ALL_IN: today_prices}
    tomorrow = {
        PriceType.MARKET_WITH_VAT: tomorrow_prices,
        PriceType.ALL_IN: all_in_tomorrow,
    }
    tomorrow_result = EnergyZeroNoDataError() if missing_tomorrow else tomorrow
    mock_energyzero.get_electricity_prices.side_effect = [
        today,
        tomorrow_result,
        today,
        tomorrow_result,
        tomorrow,
        EnergyZeroNoDataError(),
    ]
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ELECTRICITY_PRICE_INTERVAL: selected}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.move_to("2026-04-10 21:52:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_energyzero.get_electricity_prices.await_count == 4
    for entity_id, value in (
        ("sensor.energyzero_today_energy_next_hour_price", 0.0),
        ("sensor.energyzero_today_energy_all_in_next_price", 0.11),
    ):
        assert (state := hass.states.get(entity_id))
        assert state.state == (STATE_UNKNOWN if missing_tomorrow else str(value))

    freezer.move_to("2026-04-10 22:00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert diagnostics["electricity_market"]["next_price"] == (
        None if missing_tomorrow else 0.01
    )
    assert diagnostics["electricity_all_in"]["next_price"] == (
        None if missing_tomorrow else 0.12
    )
    assert mock_energyzero.get_electricity_prices.await_count == 4

    freezer.move_to("2026-04-10 22:02:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    for entity_id, value in (
        ("sensor.energyzero_today_energy_next_hour_price", 0.01),
        ("sensor.energyzero_today_energy_all_in_next_price", 0.12),
    ):
        assert (state := hass.states.get(entity_id))
        assert state.state == str(value)
    assert mock_energyzero.get_electricity_prices.await_count == 6
