"""Tests for the EnergyZero integration."""

from datetime import date
from unittest.mock import MagicMock, call, patch
from zoneinfo import ZoneInfo

from energyzero import EnergyZeroConnectionError, Interval, PriceType
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.freeze_time("2026-04-10 20:32:59")
async def test_coordinator_requests_market_prices_with_vat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energyzero: MagicMock,
) -> None:
    """Test the coordinator requests the backwards-compatible price stream."""
    mock_config_entry.add_to_hass(hass)
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
                interval=Interval.HOUR,
                price_type=PriceType.MARKET_WITH_VAT,
                local_tz=local_tz,
            ),
            call(
                start_date=tomorrow,
                end_date=tomorrow,
                interval=Interval.HOUR,
                price_type=PriceType.MARKET_WITH_VAT,
                local_tz=local_tz,
            ),
        ]
    )
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
