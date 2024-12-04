"""Test Suez_water integration initialization."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.suez_water.const import CONF_COUNTER_ID, DOMAIN
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.suez_water.const import DATA_REFRESH_INTERVAL
from homeassistant.components.suez_water.coordinator import (
    CONF_COUNTER_ID,
    DOMAIN,
    DayDataResult,
    PySuezError,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import setup_integration
from .conftest import MOCK_DATA

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_initialization_invalid_credentials(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that suez_water can't be loaded with invalid credentials."""

    suez_client.check_credentials.return_value = False
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_initialization_setup_api_error(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that suez_water needs to retry loading if api failed to connect."""

    suez_client.check_credentials.side_effect = PySuezError("Test failure")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "statistic",
    [
        "water_cost_statistics",
        "water_consumption_statistics",
    ],
)
async def test_statistics(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    statistic: str,
) -> None:
    """Test that suez_water statisticts are working."""
    nb_samples = 120

    start = datetime.fromisoformat("2024-12-04T02:00:00.0")
    freezer.move_to(start)

    origin = dt_util.start_of_local_day(start.date()) - timedelta(days=nb_samples)
    result = [
        DayDataResult((origin + timedelta(days=d)).date(), 500, 500 * (d + 1))
        for d in range(nb_samples)
    ]
    suez_client.fetch_all_daily_data.return_value = result

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Init data retrieved
    await _test_for_data(
        hass,
        suez_client,
        snapshot,
        statistic,
        origin,
        mock_config_entry.data[CONF_COUNTER_ID],
        1,
    )

    # No new data retrieved
    suez_client.fetch_all_daily_data.return_value = []
    freezer.tick(DATA_REFRESH_INTERVAL)
    async_fire_time_changed(hass)

    await _test_for_data(
        hass,
        suez_client,
        snapshot,
        statistic,
        origin,
        mock_config_entry.data[CONF_COUNTER_ID],
        2,
    )
    # Old data retrieved
    suez_client.fetch_all_daily_data.return_value = [
        DayDataResult(origin.date() - timedelta(days=1), 500, 500 * (121 + 1))
    ]
    freezer.tick(DATA_REFRESH_INTERVAL)
    async_fire_time_changed(hass)

    await _test_for_data(
        hass,
        suez_client,
        snapshot,
        statistic,
        origin,
        mock_config_entry.data[CONF_COUNTER_ID],
        3,
    )

    # New daily data retrieved
    suez_client.fetch_all_daily_data.return_value = [
        DayDataResult(datetime.now().date(), 500, 500 * (121 + 1))
    ]
    freezer.tick(DATA_REFRESH_INTERVAL)
    async_fire_time_changed(hass)

    await _test_for_data(
        hass,
        suez_client,
        snapshot,
        statistic,
        origin,
        mock_config_entry.data[CONF_COUNTER_ID],
        4,
    )


async def _test_for_data(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    snapshot: SnapshotAssertion,
    statistic: str,
    origin: datetime,
    counter_id: str,
    nb_calls: int,
) -> None:
    await hass.async_block_till_done(True)
    await async_wait_recording_done(hass)

    assert suez_client.fetch_all_daily_data.call_count == nb_calls
    statistic_id = f"{DOMAIN}:{counter_id}_{statistic}"
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        origin - timedelta(days=1),
        None,
        [statistic_id],
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )
    assert stats == snapshot(name=f"test_statistics_call{nb_calls}")


async def test_migration_version_rollback(
    hass: HomeAssistant,
    suez_client: AsyncMock,
) -> None:
    """Test that downgrading from a future version is not possible."""
    future_entry = MockConfigEntry(
        unique_id=MOCK_DATA[CONF_COUNTER_ID],
        domain=DOMAIN,
        title="Suez mock device",
        data=MOCK_DATA,
        version=3,
    )
    await setup_integration(hass, future_entry)
    assert future_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_no_migration_current_version(
    hass: HomeAssistant,
    suez_client: AsyncMock,
) -> None:
    """Test that a current version does not migrate."""
    current_entry = MockConfigEntry(
        unique_id=MOCK_DATA[CONF_COUNTER_ID],
        domain=DOMAIN,
        title="Suez mock device",
        data=MOCK_DATA,
        version=2,
    )
    await setup_integration(hass, current_entry)
    assert current_entry.state is ConfigEntryState.LOADED
    assert current_entry.unique_id == MOCK_DATA[CONF_COUNTER_ID]


async def test_migration_version_1_to_2(
    hass: HomeAssistant,
    suez_client: AsyncMock,
) -> None:
    """Test that a migration from 1 to 2 changes the unique_id."""
    past_entry = MockConfigEntry(
        unique_id=MOCK_DATA[CONF_USERNAME],
        domain=DOMAIN,
        title=MOCK_DATA[CONF_USERNAME],
        data=MOCK_DATA,
        version=1,
    )

    await setup_integration(hass, past_entry)
    assert past_entry.state is ConfigEntryState.LOADED
    assert past_entry.unique_id == MOCK_DATA[CONF_COUNTER_ID]
    assert past_entry.title == MOCK_DATA[CONF_USERNAME]
    assert past_entry.version == 2
