"""Tests for the Opower coordinator."""

from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any
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


async def test_coordinator_uses_import_export_registers(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test the meter's own import/export registers are preferred over the net.

    An interval that is net-export can still contain real grid import, so
    splitting the net on its sign undercounts both directions. When the utility
    publishes the registers we use them verbatim.
    """
    mock_opower_api.async_get_cost_reads.return_value = [
        # Net export, but 0.25 kWh really was taken from the grid in that hour.
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 8)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            consumption=-3.9,
            provided_cost=-1.2,
            imported=0.25,
            exported=4.15,
        ),
        # Net import, with a little export in the same hour.
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 10)),
            consumption=1.5,
            provided_cost=0.5,
            imported=1.75,
            exported=0.25,
        ),
    ]

    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

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

    consumption = stats["opower:pge_elec_111111_energy_consumption"]
    grid_return = stats["opower:pge_elec_111111_energy_return"]
    # Sign splitting would have recorded 0 and 1.5 for consumption
    # and 3.9 and 0 for return.
    assert [s["state"] for s in consumption] == [0.25, 1.75]
    assert [s["sum"] for s in consumption] == [0.25, 2.0]
    assert [s["state"] for s in grid_return] == [4.15, 0.25]
    assert [s["sum"] for s in grid_return] == [4.15, 4.4]


async def test_coordinator_falls_back_to_sign_split(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test reads without registers still split the net on its sign.

    Utilities that do not publish the registers leave both fields None, and even
    those that do can leave gaps (PG&E publishes none for the hours around a DST
    transition), so both paths have to coexist within a single update.
    """
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 8)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            consumption=-3.9,
            provided_cost=-1.2,
        ),
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 10)),
            consumption=1.5,
            provided_cost=0.5,
            imported=1.75,
            exported=0.25,
        ),
        # Only one of the two registers came back; not enough to use either.
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 10)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 11)),
            consumption=2.0,
            provided_cost=0.7,
            imported=2.0,
        ),
    ]

    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

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

    assert [s["state"] for s in stats["opower:pge_elec_111111_energy_consumption"]] == [
        0.0,
        1.75,
        2.0,
    ]
    assert [s["state"] for s in stats["opower:pge_elec_111111_energy_return"]] == [
        3.9,
        0.25,
        0.0,
    ]


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
    issue_registry: ir.IssueRegistry,
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
    issue_registry: ir.IssueRegistry,
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

    # Migration should return False and not create an issue if
    # no individual stats were found
    assert migrated is False

    issue = issue_registry.async_get_issue(DOMAIN, "return_to_grid_migration_111111")
    assert issue is None


async def test_coordinator_migration_negative_state(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test negative consumption migrated to return-to-grid stats."""
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

    # Check that the return-to-grid stat was created with the
    # absolute value of the negative consumption
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


async def test_coordinator_skips_update_when_hourly_reads_are_empty(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test that an empty hourly response does not write daily data over hourly data.

    The account provides hourly reads, so an empty hourly response is a
    transient failure. Falling back to the daily reads would write a day
    resolution statistic at the same timestamp as the first hourly statistic of
    that day, carrying a different running sum, which corrupts the series.
    """
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    account = mock_opower_api.async_get_accounts.return_value[0]
    mock_opower_api.async_get_accounts.return_value = [account]

    statistic_id = "opower:pge_elec_111111_energy_consumption"
    # 08:00 UTC is local midnight for the utility's timezone in January.
    day1 = dt_util.as_utc(datetime(2023, 1, 1, 8))
    day2 = dt_util.as_utc(datetime(2023, 1, 2, 8))
    day3 = dt_util.as_utc(datetime(2023, 1, 3, 8))

    def bill_reads() -> list[CostRead]:
        return [
            CostRead(
                start_time=day1,
                end_time=dt_util.as_utc(datetime(2023, 2, 1, 8)),
                consumption=60.0,
                provided_cost=12.0,
            )
        ]

    def daily_reads() -> list[CostRead]:
        return [
            CostRead(
                start_time=start, end_time=end, consumption=30.0, provided_cost=6.0
            )
            for start, end in ((day1, day2), (day2, day3))
        ]

    def hourly_reads() -> list[CostRead]:
        return [
            CostRead(
                start_time=day + timedelta(hours=hour),
                end_time=day + timedelta(hours=hour + 1),
                consumption=1.5,
                provided_cost=0.3,
            )
            for day in (day1, day2)
            for hour in range(3)
        ]

    async def all_resolutions(acc, aggregate_type, start, end):
        return {
            AggregateType.BILL: bill_reads(),
            AggregateType.DAY: daily_reads(),
            AggregateType.HOUR: hourly_reads(),
        }[aggregate_type]

    mock_opower_api.async_get_cost_reads.side_effect = all_resolutions
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    async def stats() -> list[dict[str, Any]]:
        period_stats = await hass.async_add_executor_job(
            statistics_during_period,
            hass,
            day1,
            None,
            {statistic_id},
            "hour",
            None,
            {"start", "state", "sum"},
        )
        return period_stats[statistic_id]

    before = await stats()
    assert len(before) == len(hourly_reads())

    # The hourly endpoint transiently returns nothing.
    async def no_hourly(acc, aggregate_type, start, end):
        return {
            AggregateType.BILL: bill_reads(),
            AggregateType.DAY: daily_reads(),
            AggregateType.HOUR: [],
        }[aggregate_type]

    mock_opower_api.async_get_cost_reads.side_effect = no_hourly
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    after = await stats()
    assert after == before
    # Every sum must still be the previous sum plus that hour's state. A daily
    # read written at local midnight breaks this because it carries its own sum.
    for previous, current in pairwise(after):
        assert current["sum"] == pytest.approx(previous["sum"] + current["state"])


async def test_coordinator_skips_update_when_daily_reads_are_empty(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test that an empty daily response does not write bill data over daily data."""
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    # The gas account provides daily reads.
    account = mock_opower_api.async_get_accounts.return_value[1]
    mock_opower_api.async_get_accounts.return_value = [account]

    statistic_id = "opower:pge_gas_222222_energy_consumption"
    jan1 = dt_util.as_utc(datetime(2023, 1, 1, 8))
    feb1 = dt_util.as_utc(datetime(2023, 2, 1, 8))
    mar1 = dt_util.as_utc(datetime(2023, 3, 1, 8))

    # Two bill periods, so the second one is not skipped as the starting anchor.
    # The coordinator splices the finer reads into the list it is given, so each
    # call has to hand back a fresh list.
    def bill_reads() -> list[CostRead]:
        return [
            CostRead(
                start_time=jan1, end_time=feb1, consumption=60.0, provided_cost=12.0
            ),
            CostRead(
                start_time=feb1, end_time=mar1, consumption=55.0, provided_cost=11.0
            ),
        ]

    def daily_reads() -> list[CostRead]:
        return [
            CostRead(
                start_time=start,
                end_time=start + timedelta(days=1),
                consumption=2.0,
                provided_cost=0.4,
            )
            for start in (jan1, jan1 + timedelta(days=1), feb1)
        ]

    async def all_resolutions(acc, aggregate_type, start, end):
        return {
            AggregateType.BILL: bill_reads(),
            AggregateType.DAY: daily_reads(),
        }[aggregate_type]

    mock_opower_api.async_get_cost_reads.side_effect = all_resolutions
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    async def stats() -> list[dict[str, Any]]:
        period_stats = await hass.async_add_executor_job(
            statistics_during_period,
            hass,
            jan1,
            None,
            {statistic_id},
            "hour",
            None,
            {"start", "state", "sum"},
        )
        return period_stats[statistic_id]

    before = await stats()
    assert len(before) == len(daily_reads())

    # The daily endpoint transiently returns nothing.
    async def no_daily(acc, aggregate_type, start, end):
        return {AggregateType.BILL: bill_reads(), AggregateType.DAY: []}[aggregate_type]

    mock_opower_api.async_get_cost_reads.side_effect = no_daily
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    after = await stats()
    assert after == before
    for previous, current in pairwise(after):
        assert current["sum"] == pytest.approx(previous["sum"] + current["state"])


async def test_coordinator_initial_import_keeps_older_billing_history(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test that an account with only history older than the finer windows imports.

    The daily reads are fetched for the last three years and the hourly ones for
    the last two months, so an account whose data ends before those windows
    returns nothing for both. There are no statistics to overwrite on the first
    import, so the bill reads it does return must still be stored.
    """
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    account = mock_opower_api.async_get_accounts.return_value[0]
    mock_opower_api.async_get_accounts.return_value = [account]

    statistic_id = "opower:pge_elec_111111_energy_consumption"
    old = dt_util.as_utc(datetime(2015, 1, 1, 8))

    async def only_bills(acc, aggregate_type, start, end):
        if aggregate_type is not AggregateType.BILL:
            return []
        return [
            CostRead(
                start_time=old + timedelta(days=31 * month),
                end_time=old + timedelta(days=31 * (month + 1)),
                consumption=100.0,
                provided_cost=20.0,
            )
            for month in range(3)
        ]

    mock_opower_api.async_get_cost_reads.side_effect = only_bills
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        old,
        None,
        {statistic_id},
        "hour",
        None,
        {"start", "state", "sum"},
    )
    # The first read starts the series, so it is stored along with the rest.
    assert len(stats[statistic_id]) == 3
    assert stats[statistic_id][-1]["sum"] == pytest.approx(300.0)


async def test_coordinator_uses_hourly_reads_when_daily_are_empty(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test that an empty daily response still lets the hourly reads through.

    Daily and hourly reads come from the same endpoint at different aggregations,
    so one can fail while the other succeeds. Skipping on the empty daily
    response would silently drop hourly statistics for as long as that lasts.
    Only the bill reads have to be dropped, since they are the ones that would
    overwrite finer statistics.
    """
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    account = mock_opower_api.async_get_accounts.return_value[0]
    mock_opower_api.async_get_accounts.return_value = [account]

    statistic_id = "opower:pge_elec_111111_energy_consumption"
    day1 = dt_util.as_utc(datetime(2023, 1, 1, 8))
    day2 = dt_util.as_utc(datetime(2023, 1, 2, 8))

    def bill_reads() -> list[CostRead]:
        return [
            CostRead(
                start_time=day1,
                end_time=dt_util.as_utc(datetime(2023, 2, 1, 8)),
                consumption=60.0,
                provided_cost=12.0,
            )
        ]

    def hourly_reads(days: tuple[datetime, ...]) -> list[CostRead]:
        return [
            CostRead(
                start_time=day + timedelta(hours=hour),
                end_time=day + timedelta(hours=hour + 1),
                consumption=1.5,
                provided_cost=0.3,
            )
            for day in days
            for hour in range(3)
        ]

    async def all_resolutions(acc, aggregate_type, start, end):
        return {
            AggregateType.BILL: bill_reads(),
            AggregateType.DAY: [
                CostRead(
                    start_time=day1, end_time=day2, consumption=30.0, provided_cost=6.0
                )
            ],
            AggregateType.HOUR: hourly_reads((day1,)),
        }[aggregate_type]

    mock_opower_api.async_get_cost_reads.side_effect = all_resolutions
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # The daily endpoint fails while the hourly one returns a new day of reads.
    async def no_daily(acc, aggregate_type, start, end):
        return {
            AggregateType.BILL: bill_reads(),
            AggregateType.DAY: [],
            AggregateType.HOUR: hourly_reads((day1, day2)),
        }[aggregate_type]

    mock_opower_api.async_get_cost_reads.side_effect = no_daily
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        day1,
        None,
        {statistic_id},
        "hour",
        None,
        {"start", "state", "sum"},
    )
    rows = stats[statistic_id]
    # The second day's hourly reads were stored rather than skipped.
    assert len(rows) == 6
    assert rows[-1]["sum"] == pytest.approx(9.0)
    for previous, current in pairwise(rows):
        assert current["sum"] == pytest.approx(previous["sum"] + current["state"])
