"""Test Suez_water integration initialization."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.suez_water.const import (
    CONF_COUNTER_ID,
    DATA_REFRESH_INTERVAL,
    DOMAIN,
)
from homeassistant.components.suez_water.coordinator import (
    PySuezError,
    TelemetryMeasure,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import setup_integration
from .conftest import MOCK_DATA

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_initialization_setup_api_error(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that suez_water needs to retry loading if api failed to connect."""

    suez_client.check_credentials.side_effect = PySuezError("Test failure")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_init_auth_failed(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that suez_water reflect authentication failure."""
    suez_client.check_credentials.return_value = False
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_init_refresh_failed(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that suez_water reflect authentication failure."""
    suez_client.fetch_aggregated_data.side_effect = PySuezError("Update failed")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_init_statistics_failed(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that suez_water reflect authentication failure."""
    suez_client.fetch_all_daily_data.side_effect = PySuezError("Update failed")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("recorder_mock")
async def test_statistics_no_price(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that suez_water statistics does not register when no price."""
    # New data retrieved but no price
    suez_client.get_price.side_effect = PySuezError("will fail")
    suez_client.fetch_all_daily_data.return_value = [
        TelemetryMeasure(
            dt_util.utcnow().date().strftime("%Y-%m-%d %H:%M:%S"),
            0.5,
            0.5,
        )
    ]

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    statistic_id = (
        f"{DOMAIN}:{mock_config_entry.data[CONF_COUNTER_ID]}_water_cost_statistics"
    )
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utcnow() - timedelta(days=1),
        None,
        [statistic_id],
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )

    assert stats.get(statistic_id) is None


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
    """Test that suez_water statistics are working."""
    nb_samples = 3

    start = datetime.fromisoformat("2024-12-04T02:00:00.0")
    freezer.move_to(start)

    origin = dt_util.start_of_local_day(start.date()) - timedelta(days=nb_samples)
    result = [
        TelemetryMeasure(
            date=((origin + timedelta(days=d)).date()).strftime("%Y-%m-%d %H:%M:%S"),
            volume=0.5,
            index=0.5 * (d + 1),
        )
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
        TelemetryMeasure(
            date=(origin.date() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            volume=0.5,
            index=0.5 * (121 + 1),
        )
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
        TelemetryMeasure(
            date=dt_util.utcnow().date().strftime("%Y-%m-%d %H:%M:%S"),
            volume=0.5,
            index=0.5 * (121 + 1),
        )
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


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    ("duplicate_volume", "expected_log_level"),
    [
        (100.0, "debug"),
        (999.0, "warning"),
    ],
)
async def test_statistics_with_duplicate_dates(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    duplicate_volume: float,
    expected_log_level: str,
) -> None:
    """Test that duplicate dates in data are handled correctly."""
    start = datetime.fromisoformat("2024-12-04T02:00:00.0")
    freezer.move_to(start)

    origin = dt_util.start_of_local_day(start.date()) - timedelta(days=3)

    result = [
        TelemetryMeasure(
            date=origin.date().strftime("%Y-%m-%d %H:%M:%S"),
            volume=0.1,
            index=0.1,
        ),
        TelemetryMeasure(
            date=(origin + timedelta(days=1)).date().strftime("%Y-%m-%d %H:%M:%S"),
            volume=0.15,
            index=0.25,
        ),
        TelemetryMeasure(
            date=(origin + timedelta(days=2)).date().strftime("%Y-%m-%d %H:%M:%S"),
            volume=0.2,
            index=0.45,
        ),
        # Duplicate of the first day with same or different volume
        TelemetryMeasure(
            date=origin.date().strftime("%Y-%m-%d %H:%M:%S"),
            volume=duplicate_volume / 1000,  # Convert L to m³
            index=0.1,
        ),
    ]
    suez_client.fetch_all_daily_data.return_value = result

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    await hass.async_block_till_done(True)
    await async_wait_recording_done(hass)

    statistic_id = f"{DOMAIN}:{mock_config_entry.data[CONF_COUNTER_ID]}_water_consumption_statistics"
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        origin - timedelta(days=1),
        None,
        [statistic_id],
        "hour",
        None,
        {"start", "state", "sum"},
    )

    # Verify that we only have 3 entries (not 4), and the duplicate was ignored
    assert statistic_id in stats
    assert len(stats[statistic_id]) == 3

    # Verify the cumulative sum is correct (100 + 150 + 200 = 450, not 550)
    assert stats[statistic_id][0]["sum"] == 100.0
    assert stats[statistic_id][1]["sum"] == 250.0
    assert stats[statistic_id][2]["sum"] == 450.0

    # Verify appropriate log message based on whether values differ
    if expected_log_level == "warning":
        assert any(
            "Duplicate date" in record.message and "different volume" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )
    else:
        assert any(
            "Skipping duplicate date" in record.message
            for record in caplog.records
            if record.levelname == "DEBUG"
        )
