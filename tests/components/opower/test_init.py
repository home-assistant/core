"""Tests for the Opower integration."""

from datetime import datetime
from unittest.mock import AsyncMock

from opower import CostRead
from opower.exceptions import ApiException, CannotConnect, InvalidAuth
import pytest

from homeassistant.components.opower.const import DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
from tests.components.recorder.common import async_wait_recording_done


async def test_setup_unload_entry(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test successful setup and unload of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_opower_api.async_login.assert_awaited_once()
    mock_opower_api.async_get_bills.assert_awaited_once()
    mock_opower_api.async_get_forecast.assert_awaited_once()
    mock_opower_api.async_get_accounts.assert_awaited_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.parametrize(
    ("login_side_effect", "expected_state"),
    [
        (
            CannotConnect(),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            InvalidAuth(),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_login_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    login_side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test for login error."""
    mock_opower_api.async_login.side_effect = login_side_effect

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_get_forecast_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test for API error when getting forecast."""
    mock_opower_api.async_get_forecast.side_effect = ApiException(
        message="forecast error", url=""
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_accounts_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test for API error when getting accounts."""
    mock_opower_api.async_get_accounts.side_effect = ApiException(
        message="accounts error", url=""
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "bills_side_effect",
    [
        ApiException(message="completed bills error", url=""),
        CannotConnect(),
    ],
)
async def test_get_bills_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    bills_side_effect: Exception,
) -> None:
    """Test a completed bills error does not block forecasts or statistics."""
    mock_opower_api.async_get_bills.side_effect = bills_side_effect
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 8)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            consumption=1.5,
            provided_cost=0.5,
        )
    ]

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    forecast_state = hass.states.get(
        "sensor.elec_account_111111_current_bill_electric_usage_to_date"
    )
    assert forecast_state
    assert forecast_state.state == "100"
    assert (
        hass.states.get("sensor.elec_account_111111_last_bill_electricity_rate") is None
    )

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {"opower:pge_elec_111111_energy_consumption"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats["opower:pge_elec_111111_energy_consumption"][0]["state"] == 1.5


async def test_get_cost_reads_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test for API error when getting cost reads."""
    mock_opower_api.async_get_cost_reads.side_effect = ApiException(
        message="cost reads error", url=""
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
