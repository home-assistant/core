"""Tests for the EnergyZero integration."""

from datetime import date
from unittest.mock import MagicMock, call, patch
from zoneinfo import ZoneInfo

from energyzero import (
    EnergyPrices,
    EnergyZeroConnectionError,
    EnergyZeroNoDataError,
    Interval,
    PriceType,
)
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
@pytest.mark.parametrize(
    "missing_types",
    [
        pytest.param((PriceType.MARKET_WITH_VAT,), id="market"),
        pytest.param((PriceType.ALL_IN,), id="all_in"),
        pytest.param((PriceType.MARKET_WITH_VAT, PriceType.ALL_IN), id="both"),
    ],
)
async def test_partial_tomorrow_prices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energyzero: MagicMock,
    missing_types: tuple[PriceType, ...],
) -> None:
    """Missing optional streams do not discard the available tomorrow stream."""
    original_side_effect = mock_energyzero.get_electricity_prices.side_effect

    def get_prices(
        *,
        start_date: date,
        end_date: date,
        interval: Interval,
        price_type: PriceType | tuple[PriceType, ...],
        local_tz: ZoneInfo,
    ) -> EnergyPrices | dict[PriceType, EnergyPrices]:
        price_types = price_type
        requested_types = (
            (price_types,) if isinstance(price_types, PriceType) else price_types
        )
        if start_date == date(2026, 4, 11) and set(requested_types) & set(
            missing_types
        ):
            raise EnergyZeroNoDataError
        return original_side_effect(
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            price_type=price_type,
            local_tz=local_tz,
        )

    mock_energyzero.get_electricity_prices.side_effect = get_prices
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    data = mock_config_entry.runtime_data.data
    assert (data.electricity_market_tomorrow is None) == (
        PriceType.MARKET_WITH_VAT in missing_types
    )
    assert (data.electricity_all_in_tomorrow is None) == (
        PriceType.ALL_IN in missing_types
    )
    assert hass.states.get("sensor.energyzero_today_energy_current_hour_price")
    assert hass.states.get("sensor.energyzero_today_energy_all_in_current_price")


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
