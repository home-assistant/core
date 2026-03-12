"""Tests for the Opower coordinator."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from opower import AggregateType, CostRead
from opower.exceptions import ApiException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.opower.const import DOMAIN
from homeassistant.components.opower.coordinator import OpowerCoordinator
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from tests.common import MockConfigEntry
from tests.components.recorder.common import async_wait_recording_done


async def test_coordinator_first_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator on its first run with no existing statistics."""
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 8)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            consumption=1.5,
            provided_cost=0.5,
        ),
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 10)),
            consumption=-0.5,  # Grid return
            provided_cost=-0.1,  # Compensation
        ),
    ]

    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()

    await async_wait_recording_done(hass)

    # Check stats for electric account '111111'
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {
            "opower:pge_elec_111111_energy_consumption",
            "opower:pge_elec_111111_energy_return",
            "opower:pge_elec_111111_energy_cost",
            "opower:pge_elec_111111_energy_compensation",
        },
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == snapshot


async def test_coordinator_subsequent_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator correctly updates statistics on subsequent runs."""
    # First run
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 8)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            consumption=1.5,
            provided_cost=0.5,
        ),
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 10)),
            consumption=-0.5,
            provided_cost=-0.1,
        ),
    ]
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Second run with updated data for one hour and new data for the next hour
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),  # Updated data
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 10)),
            consumption=-1.0,  # Was -0.5
            provided_cost=-0.2,  # Was -0.1
        ),
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 10)),  # New data
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 11)),
            consumption=2.0,
            provided_cost=0.7,
        ),
    ]
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Check all stats
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {
            "opower:pge_elec_111111_energy_consumption",
            "opower:pge_elec_111111_energy_return",
            "opower:pge_elec_111111_energy_cost",
            "opower:pge_elec_111111_energy_compensation",
        },
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == snapshot


async def test_coordinator_subsequent_run_no_energy_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator handles no recent usage/cost data."""
    # First run
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 8)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            consumption=1.5,
            provided_cost=0.5,
        ),
    ]
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Second run with no data
    mock_opower_api.async_get_cost_reads.return_value = []

    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()

    assert "No recent usage/cost data. Skipping update" in caplog.text

    # Verify no new stats were added by checking the sum remains 1.5
    statistic_id = "opower:pge_elec_111111_energy_consumption"
    stats = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )
    assert stats[statistic_id][0]["sum"] == 1.5


async def test_coordinator_migration(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the one-time migration for return-to-grid statistics."""
    # Setup: Create old-style consumption data with negative values
    statistic_id = "opower:pge_elec_111111_energy_consumption"
    metadata = StatisticMetaData(
        has_sum=True,
        mean_type=StatisticMeanType.NONE,
        name="Opower pge elec 111111 consumption",
        source=DOMAIN,
        statistic_id=statistic_id,
        unit_class=EnergyConverter.UNIT_CLASS,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    )
    statistics_to_add = [
        StatisticData(
            start=dt_util.as_utc(datetime(2023, 1, 1, 8)),
            state=1.5,
            sum=1.5,
        ),
        StatisticData(
            start=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            state=-0.5,  # This should be migrated
            sum=1.0,
        ),
    ]
    async_add_external_statistics(hass, metadata, statistics_to_add)
    await async_wait_recording_done(hass)

    # When the coordinator runs, it should trigger the migration
    # Don't need new cost reads for this test
    mock_opower_api.async_get_cost_reads.return_value = []

    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Check that the stats have been migrated
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {
            "opower:pge_elec_111111_energy_consumption",
            "opower:pge_elec_111111_energy_return",
        },
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == snapshot

    # Check that an issue was created
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "return_to_grid_migration_111111")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING


@pytest.mark.parametrize(
    ("method", "aggregate_type"),
    [
        ("async_get_accounts", None),
        ("async_get_forecast", None),
        ("async_get_cost_reads", AggregateType.BILL),
        ("async_get_cost_reads", AggregateType.DAY),
        ("async_get_cost_reads", AggregateType.HOUR),
    ],
)
async def test_coordinator_api_exceptions(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    method: str,
    aggregate_type: AggregateType | None,
) -> None:
    """Test the coordinator handles API exceptions during data fetching."""
    coordinator = OpowerCoordinator(hass, mock_config_entry)

    if method == "async_get_cost_reads":

        async def side_effect(account, agg_type, start, end):
            if agg_type == aggregate_type:
                raise ApiException(message="Error", url="http://example.com")
            # For other calls, return some dummy data to proceed if needed
            return [
                CostRead(
                    start_time=dt_util.utcnow() - timedelta(days=1),
                    end_time=dt_util.utcnow(),
                    consumption=1.0,
                    provided_cost=0.1,
                )
            ]

        mock_opower_api.async_get_cost_reads.side_effect = side_effect
    else:
        getattr(mock_opower_api, method).side_effect = ApiException(
            message="Error", url="http://example.com"
        )

    with pytest.raises(ApiException):
        await coordinator._async_update_data()


async def test_coordinator_updates_with_finer_grained_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test that coarse data is updated when finer-grained data becomes available."""
    coordinator = OpowerCoordinator(hass, mock_config_entry)

    # Mock accounts to return only one account to simplify
    account = mock_opower_api.async_get_accounts.return_value[0]
    mock_opower_api.async_get_accounts.return_value = [account]

    t1 = dt_util.as_utc(datetime(2023, 1, 1, 0))
    t2 = dt_util.as_utc(datetime(2023, 1, 2, 0))

    def mock_get_cost_reads(acc, aggregate_type, start, end):
        if aggregate_type == AggregateType.BILL:
            # Coarse bill data
            return [
                CostRead(
                    start_time=t1, end_time=t2, consumption=10.0, provided_cost=2.0
                )
            ]
        if aggregate_type == AggregateType.DAY:
            # Finer day data starting at the same time
            return [
                CostRead(
                    start_time=t1,
                    end_time=t1 + timedelta(hours=12),
                    consumption=5.0,
                    provided_cost=1.0,
                )
            ]
        if aggregate_type == AggregateType.HOUR:
            # Even finer hour data starting later
            return [
                CostRead(
                    start_time=t1 + timedelta(hours=12),
                    end_time=t1 + timedelta(hours=13),
                    consumption=1.0,
                    provided_cost=0.2,
                )
            ]
        return []

    mock_opower_api.async_get_cost_reads.side_effect = mock_get_cost_reads

    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Verify that we have statistics for the electric account
    statistic_id = "opower:pge_elec_111111_energy_consumption"
    # Check the last statistic to ensure data was written at all
    last_stats = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )
    assert statistic_id in last_stats
    assert last_stats[statistic_id][0]["sum"] > 0
    # Check statistics over the full period to ensure finer-grained data was stored
    period_stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        t1,
        t2,
        {statistic_id},
        "hour",
        None,
        {"sum"},
    )
    assert statistic_id in period_stats
    # If only a single coarse (e.g., monthly) point were stored for this 1-day
    # interval, we would see at most one data point here. More than one point
    # indicates that finer-grained reads have been merged into the statistics.
    assert len(period_stats[statistic_id]) > 1


async def test_coordinator_migration_empty_source_stats(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test migration logic when source statistics are unexpectedly missing."""
    statistic_id = "opower:pge_elec_111111_energy_consumption"
    target_id = "opower:pge_elec_111111_energy_return"

    coordinator = OpowerCoordinator(hass, mock_config_entry)

    with patch(
        "homeassistant.components.opower.coordinator.statistics_during_period",
        return_value={statistic_id: []},
    ):
        migrated = await coordinator._async_maybe_migrate_statistics(
            "111111",
            {statistic_id: target_id},
            {
                statistic_id: StatisticMetaData(
                    has_sum=True,
                    mean_type=StatisticMeanType.NONE,
                    name="c",
                    source=DOMAIN,
                    statistic_id=statistic_id,
                    unit_class=EnergyConverter.UNIT_CLASS,
                    unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                ),
                target_id: StatisticMetaData(
                    has_sum=True,
                    mean_type=StatisticMeanType.NONE,
                    name="r",
                    source=DOMAIN,
                    statistic_id=target_id,
                    unit_class=EnergyConverter.UNIT_CLASS,
                    unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                ),
            },
        )

    # Migration should return False and not create an issue if no individual stats were found
    assert migrated is False

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "return_to_grid_migration_111111")
    assert issue is None


async def test_coordinator_migration_negative_state(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test that negative consumption states are correctly migrated to return-to-grid statistics."""
    statistic_id = "opower:pge_elec_111111_energy_consumption"
    target_id = "opower:pge_elec_111111_energy_return"
    metadata = StatisticMetaData(
        has_sum=True,
        mean_type=StatisticMeanType.NONE,
        name="Opower pge elec 111111 consumption",
        source=DOMAIN,
        statistic_id=statistic_id,
        unit_class=EnergyConverter.UNIT_CLASS,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    )
    statistics_to_add = [
        StatisticData(
            start=dt_util.as_utc(datetime(2023, 1, 1, 8)), state=1.5, sum=1.5
        ),
        StatisticData(
            start=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            state=-0.5,
            sum=1.0,  # Negative consumption state
        ),
    ]
    async_add_external_statistics(hass, metadata, statistics_to_add)
    await async_wait_recording_done(hass)

    mock_opower_api.async_get_cost_reads.return_value = []
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Check that the return-to-grid stat was created with the absolute value of the negative consumption
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(2023, 1, 1, 9)),
        dt_util.as_utc(datetime(2023, 1, 1, 10)),
        {target_id},
        "hour",
        None,
        {"state"},
    )
    assert stats[target_id][0]["state"] == 0.5


async def test_coordinator_no_new_cost_reads_after_initial_load(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test that the coordinator correctly identifies when no new data is available."""
    # First run to get some stats
    t1 = dt_util.as_utc(datetime(2023, 1, 1, 8))
    t2 = dt_util.as_utc(datetime(2023, 1, 1, 9))
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=t1,
            end_time=t2,
            consumption=1.5,
            provided_cost=0.5,
        ),
    ]
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Second run: API returns data that has already been recorded
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=t1,
            end_time=t2,
            consumption=1.5,
            provided_cost=0.5,
        ),
    ]
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Sum should still be 1.5
    statistic_id = "opower:pge_elec_111111_energy_consumption"
    stats = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )
    assert stats[statistic_id][0]["sum"] == 1.5
