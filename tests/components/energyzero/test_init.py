"""Tests for the EnergyZero integration."""

from datetime import date
from unittest.mock import MagicMock, call, patch
from zoneinfo import ZoneInfo

from energyzero import EnergyZeroConnectionError, Interval, PriceType
import pytest

from homeassistant.components.energyzero.const import (
    CONF_ELECTRICITY_PRICE_INTERVAL,
    DOMAIN,
    ELECTRICITY_INTERVALS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_json_object_fixture


@pytest.mark.parametrize(
    ("options", "interval"),
    [
        pytest.param({}, Interval.HOUR, id="existing"),
        pytest.param(
            {CONF_ELECTRICITY_PRICE_INTERVAL: "hourly"}, Interval.HOUR, id="hourly"
        ),
        pytest.param(
            {CONF_ELECTRICITY_PRICE_INTERVAL: "quarter_hourly"},
            Interval.QUARTER,
            id="quarter_hourly",
        ),
    ],
)
@pytest.mark.freeze_time("2026-04-10 20:32:59")
async def test_coordinator_requests_both_prices_with_vat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energyzero: MagicMock,
    options: dict[str, str],
    interval: Interval,
) -> None:
    """Test both VAT-inclusive streams share a request and the configured interval."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    local_tz = ZoneInfo(hass.config.time_zone)
    today = date(2026, 4, 10)
    tomorrow = date(2026, 4, 11)
    mock_energyzero.get_electricity_prices.assert_has_awaits(
        [
            call(
                start_date=today,
                end_date=today,
                interval=interval,
                price_type=(PriceType.MARKET_WITH_VAT, PriceType.ALL_IN),
                local_tz=local_tz,
            ),
            call(
                start_date=tomorrow,
                end_date=tomorrow,
                interval=interval,
                price_type=(PriceType.MARKET_WITH_VAT, PriceType.ALL_IN),
                local_tz=local_tz,
            ),
        ]
    )
    assert mock_energyzero.get_electricity_prices.await_count == 2
    mock_energyzero.get_gas_prices.assert_awaited_once_with(
        start_date=today,
        end_date=today,
        price_type=PriceType.MARKET_WITH_VAT,
        local_tz=local_tz,
    )


@pytest.mark.usefixtures("mock_energyzero")
async def test_load_unload_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the EnergyZero configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@patch("energyzero.api.rest.RESTClient._request", side_effect=EnergyZeroConnectionError)
async def test_config_flow_entry_not_ready(
    mock_request: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the EnergyZero configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.freeze_time("2026-04-10 20:32:59")
@pytest.mark.parametrize("selected", ["hourly", "quarter_hourly"])
@pytest.mark.parametrize(
    "missing_streams",
    [
        pytest.param(("base_with_vat",), id="market"),
        pytest.param(("all_in_with_vat",), id="all_in"),
        pytest.param(("base_with_vat", "all_in_with_vat"), id="both"),
        pytest.param(
            ("base", "base_with_vat", "all_in", "all_in_with_vat"),
            id="unpublished",
        ),
    ],
)
async def test_missing_tomorrow_prices_do_not_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    selected: str,
    missing_streams: tuple[str, ...],
) -> None:
    """Missing tomorrow streams do not cause extra requests or fail today's sensors."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    electricity = await async_load_json_object_fixture(
        hass, "today_energy.json", DOMAIN
    )
    gas = await async_load_json_object_fixture(hass, "today_gas.json", DOMAIN)
    tomorrow = {**electricity, **{stream: [] for stream in missing_streams}}
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ELECTRICITY_PRICE_INTERVAL: selected}
    )
    with patch(
        "energyzero.api.rest.RESTClient._request",
        side_effect=[electricity, gas, tomorrow] * 2,
    ) as request:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert request.await_count == 3
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    assert request.await_count == 6
    assert (
        request.await_args_list[2]
        == request.await_args_list[5]
        == call(
            "public/v1/prices",
            params={
                "energyType": "ENERGY_TYPE_ELECTRICITY",
                "date": "11-04-2026",
                "interval": ELECTRICITY_INTERVALS[selected].value,
            },
        )
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED
    data = mock_config_entry.runtime_data.data
    assert data.electricity_market_tomorrow is None
    assert data.electricity_all_in_tomorrow is None
    assert (
        state := hass.states.get("sensor.energyzero_today_energy_current_hour_price")
    )
    assert state.state == "0.17191075"
    assert (
        state := hass.states.get("sensor.energyzero_today_energy_all_in_current_price")
    )
    assert state.state == "0.28275885"


@pytest.mark.freeze_time("2026-04-10 20:32:59")
@pytest.mark.parametrize("selected", ["hourly", "quarter_hourly"])
async def test_rest_requests_share_price_streams(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    selected: str,
) -> None:
    """The actual library extracts both streams with one REST request per day."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    electricity = await async_load_json_object_fixture(
        hass, "today_energy.json", DOMAIN
    )
    gas = await async_load_json_object_fixture(hass, "today_gas.json", DOMAIN)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ELECTRICITY_PRICE_INTERVAL: selected}
    )
    with patch(
        "energyzero.api.rest.RESTClient._request",
        side_effect=[electricity, gas, electricity],
    ) as request:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert request.await_args_list == [
        call(
            "public/v1/prices",
            params={
                "energyType": "ENERGY_TYPE_ELECTRICITY",
                "date": "10-04-2026",
                "interval": ELECTRICITY_INTERVALS[selected].value,
            },
        ),
        call(
            "public/v1/prices",
            params={
                "energyType": "ENERGY_TYPE_GAS",
                "date": "10-04-2026",
                "interval": "INTERVAL_DAY",
            },
        ),
        call(
            "public/v1/prices",
            params={
                "energyType": "ENERGY_TYPE_ELECTRICITY",
                "date": "11-04-2026",
                "interval": ELECTRICITY_INTERVALS[selected].value,
            },
        ),
    ]
    assert (
        state := hass.states.get("sensor.energyzero_today_energy_current_hour_price")
    )
    assert state.state == "0.17191075"
    assert (
        state := hass.states.get("sensor.energyzero_today_energy_all_in_current_price")
    )
    assert state.state == "0.28275885"
