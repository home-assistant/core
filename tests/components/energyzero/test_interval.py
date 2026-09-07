"""Test electricity resolution with timezone-aware price data."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from energyzero import EnergyPrices, EnergyZeroNoDataError, Interval
from energyzero.models import TimeRange
import pytest

from homeassistant.components.energyzero.const import CONF_ELECTRICITY_PRICE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
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
    mock_energyzero.get_electricity_prices.side_effect = [
        prices,
        EnergyZeroNoDataError() if missing_tomorrow else prices,
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
    data = mock_config_entry.runtime_data.data
    assert (data.energy_tomorrow is not None) == (
        requests_tomorrow and not missing_tomorrow
    )
    assert len(data.energy_today.prices) == hours * 60 // minutes
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert diagnostics["energy"]["next_price"] == expected
    assert diagnostics["energy"]["current_price"] == prices.current_price
    assert diagnostics["energy"]["average_price"] == prices.average_price
    assert (
        diagnostics["energy"]["hours_priced_equal_or_lower"]
        == prices.time_ranges_priced_equal_or_lower
    )
    assert (
        mock_energyzero.get_electricity_prices.call_args.kwargs["interval"] == interval
    )
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 11
    assert all(
        entry.unique_id == f"12345_{entry.entity_id.removeprefix('sensor.energyzero_')}"
        for entry in entries
    )
