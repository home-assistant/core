"""Tests for the Opower coordinator."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from opower import AggregateType, CostRead, ReadComponent, ReadResolution
from opower.exceptions import ApiException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.opower.const import DOMAIN
from homeassistant.components.opower.coordinator import OpowerCoordinator
from homeassistant.components.recorder import Recorder, get_instance
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


def _read_component(
    day_part: str | None,
    consumption: float,
    cost: float,
    tier_number: int | None = None,
) -> ReadComponent:
    return ReadComponent(
        tier_type="ORDINAL",
        tier_number=tier_number,
        season="SUMMER",
        day_part=day_part,
        cost=cost,
        consumption=consumption,
    )


def _rate_period_ids(*keys: str) -> set[str]:
    """Return the four statistic ids of each rate period key."""
    return {
        f"opower:pge_elec_111111_{key}_energy_{kind}"
        for key in keys
        for kind in ("consumption", "return", "cost", "compensation")
    }


async def test_coordinator_rate_periods(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test statistics per rate period are created from read components."""
    # First run: a time-of-use read, a read without components and a tiered read
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 8)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            consumption=3.0,
            provided_cost=0.75,
            read_components=[
                _read_component("ON_PEAK+RT02/TOD", 1.0, 0.5),
                _read_component("OFF_PEAK+RT02/TOD", 2.0, 0.25),
            ],
        ),
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 10)),
            consumption=1.5,
            provided_cost=0.25,
        ),
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 10)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 11)),
            consumption=2.0,
            provided_cost=0.5,
            read_components=[
                _read_component(None, 2.0, 0.5, tier_number=1),
                _read_component(None, 0.0, 0.0),  # Neither day part nor tier
            ],
        ),
    ]
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Second run: the last stored hour is refetched unchanged, as the
    # coordinator always does, and a new hour is added
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 10)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 11)),
            consumption=2.0,
            provided_cost=0.5,
            read_components=[_read_component(None, 2.0, 0.5, tier_number=1)],
        ),
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 11)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 12)),
            consumption=4.0,
            provided_cost=1.0,
            read_components=[
                _read_component("ON_PEAK+RT02/TOD", 3.0, 0.75),
                _read_component("OFF_PEAK+RT02/TOD", 1.0, 0.25),
            ],
        ),
    ]
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {
            "opower:pge_elec_111111_energy_consumption",
            "opower:pge_elec_111111_energy_cost",
        }
        | _rate_period_ids("on_peak", "off_peak", "tier_1"),
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == snapshot


async def test_coordinator_rate_periods_time_of_use_and_tiered(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test a rate that is both time-of-use and tiered keeps both in the key.

    Each combination is billed at its own price, so merging the tiers inside
    a period would throw away the split the utility bills on.
    """
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 8)),
            end_time=dt_util.as_utc(datetime(2023, 1, 2, 8)),
            consumption=12.0,
            provided_cost=4.5,
            read_components=[
                _read_component("OFF_PEAK", 6.0, 1.5, tier_number=1),
                _read_component("OFF_PEAK", 4.0, 2.0, tier_number=2),
                _read_component("PEAK", 2.0, 1.0, tier_number=1),
            ],
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
            f"opower:pge_elec_111111_{key}_energy_{kind}"
            for key in ("off_peak_tier_1", "off_peak_tier_2", "peak_tier_1")
            for kind in ("consumption", "cost")
        },
        "hour",
        None,
        {"state"},
    )
    states = {
        statistic_id.removeprefix("opower:pge_elec_111111_"): stat[0]["state"]
        for statistic_id, stat in stats.items()
    }
    assert states == {
        "off_peak_tier_1_energy_consumption": 6.0,
        "off_peak_tier_1_energy_cost": 1.5,
        "off_peak_tier_2_energy_consumption": 4.0,
        "off_peak_tier_2_energy_cost": 2.0,
        "peak_tier_1_energy_consumption": 2.0,
        "peak_tier_1_energy_cost": 1.0,
    }


async def test_coordinator_rate_periods_net_metering(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test negative components go to the period's return and compensation.

    On a net metered account a daily read can be a net export as a whole while
    one of its periods is a real import. The totals see the net; each period
    keeps its own import and export, like the totals do for the account.
    """
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 8)),
            end_time=dt_util.as_utc(datetime(2023, 1, 2, 8)),
            consumption=-5.0,
            provided_cost=-0.5,
            read_components=[
                _read_component("OFF_PEAK", 10.0, 2.0),
                _read_component("PEAK", -15.0, -2.5),
            ],
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
        }
        | _rate_period_ids("off_peak", "peak"),
        "hour",
        None,
        {"state"},
    )
    states = {
        statistic_id.removeprefix("opower:pge_elec_111111_"): stat[0]["state"]
        for statistic_id, stat in stats.items()
    }
    assert states == {
        "energy_consumption": 0.0,
        "energy_return": 5.0,
        "off_peak_energy_consumption": 10.0,
        "off_peak_energy_return": 0.0,
        "off_peak_energy_cost": 2.0,
        "off_peak_energy_compensation": 0.0,
        "peak_energy_consumption": 0.0,
        "peak_energy_return": 15.0,
        "peak_energy_cost": 0.0,
        "peak_energy_compensation": 2.5,
    }


async def test_coordinator_rate_periods_backfilled_from_full_history(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test a new rate period is backfilled from the full history.

    Once statistics exist the coordinator only fetches the last weeks of reads.
    A period without stored statistics must not start there, so the full
    history is fetched once, like the totals got on their first run.
    """
    hour = [dt_util.as_utc(datetime(2023, 1, 1, 8 + i)) for i in range(4)]
    with_components = False

    def read(index: int, consumption: float) -> CostRead:
        return CostRead(
            start_time=hour[index],
            end_time=hour[index] + timedelta(hours=1),
            consumption=consumption,
            provided_cost=consumption / 4,
            read_components=[_read_component("ON_PEAK", consumption, consumption / 4)]
            if with_components
            else [],
        )

    def mock_get_cost_reads(account, aggregate_type, start, end):
        if aggregate_type != AggregateType.BILL:
            return []
        if start is None:
            # Full history
            return [read(0, 1.0), read(1, 2.0), read(2, 4.0), read(3, 8.0)]
        # The recent window only
        return [read(2, 4.0), read(3, 8.0)]

    mock_opower_api.async_get_cost_reads.side_effect = mock_get_cost_reads
    account = mock_opower_api.async_get_accounts.return_value[0]
    account.read_resolution = ReadResolution.BILLING
    mock_opower_api.async_get_accounts.return_value = [account]

    # First run: no components yet, so only the totals are stored
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Second run: the utility now reports components
    with_components = True
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {
            "opower:pge_elec_111111_energy_consumption",
            "opower:pge_elec_111111_on_peak_energy_consumption",
        },
        "hour",
        None,
        {"sum"},
    )
    # The totals were only ever written from the reads they received
    assert [s["sum"] for s in stats["opower:pge_elec_111111_energy_consumption"]] == [
        1.0,
        3.0,
        7.0,
        15.0,
    ]
    # The period got the full history, not only the recent window
    assert [
        s["start"] for s in stats["opower:pge_elec_111111_on_peak_energy_consumption"]
    ] == [h.timestamp() for h in hour]
    assert [
        s["sum"] for s in stats["opower:pge_elec_111111_on_peak_energy_consumption"]
    ] == [1.0, 3.0, 7.0, 15.0]
    assert mock_opower_api.async_get_cost_reads.call_count == 3


async def test_coordinator_rate_periods_rebuilt_after_partial_delete(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test a period whose statistics were partly deleted is rebuilt as a whole.

    The four statistics of a period are resumed together. If one of them is
    gone, e.g. deleted in Developer tools, the period starts over from the
    full history instead of resuming the others from a point the deleted one
    no longer has.
    """
    hour = [dt_util.as_utc(datetime(2023, 1, 1, 8 + i)) for i in range(3)]
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=hour[i],
            end_time=hour[i] + timedelta(hours=1),
            consumption=float(i + 1),
            provided_cost=(i + 1) / 4,
            read_components=[_read_component("ON_PEAK", float(i + 1), (i + 1) / 4)],
        )
        for i in range(3)
    ]
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    cost_id = "opower:pge_elec_111111_on_peak_energy_cost"
    get_instance(hass).async_clear_statistics([cost_id])
    await async_wait_recording_done(hass)

    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {cost_id, "opower:pge_elec_111111_on_peak_energy_consumption"},
        "hour",
        None,
        {"sum"},
    )
    assert [s["sum"] for s in stats[cost_id]] == [0.25, 0.75, 1.5]
    assert [
        s["sum"] for s in stats["opower:pge_elec_111111_on_peak_energy_consumption"]
    ] == [1.0, 3.0, 6.0]


async def test_coordinator_rate_period_returns_after_absence(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test a rate period continues its sum after runs without it.

    Each run refetches the previous run's last read, as the coordinator
    refetches the last 30 days to allow corrections in data from utilities.
    """
    hour = [dt_util.as_utc(datetime(2023, 1, 1, 8 + i)) for i in range(5)]
    on_peak_id = "opower:pge_elec_111111_on_peak_energy_consumption"
    off_peak_id = "opower:pge_elec_111111_off_peak_energy_consumption"

    def read(index: int, components: list[ReadComponent]) -> CostRead:
        return CostRead(
            start_time=hour[index],
            end_time=hour[index + 1],
            consumption=sum(c.consumption for c in components) or 1.0,
            provided_cost=sum(c.cost for c in components) or 0.1,
            read_components=components,
        )

    # First run: on peak, then a read without components
    mock_opower_api.async_get_cost_reads.return_value = [
        read(0, [_read_component("ON_PEAK", 1.0, 0.5)]),
        read(1, []),
    ]
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Second run: only off peak, so no on peak statistics are written
    mock_opower_api.async_get_cost_reads.return_value = [
        read(1, []),
        read(2, [_read_component("OFF_PEAK", 2.0, 0.4)]),
    ]
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # On peak was last written in the first run, with a zero state at hour 1
    stats = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, on_peak_id, True, {"start", "sum"}
    )
    assert stats[on_peak_id][0]["start"] == hour[1].timestamp()
    assert stats[on_peak_id][0]["sum"] == 1.0

    # Third run: on peak is back and its sum continues from the first run
    mock_opower_api.async_get_cost_reads.return_value = [
        read(2, [_read_component("OFF_PEAK", 2.0, 0.4)]),
        read(3, [_read_component("ON_PEAK", 3.0, 1.5)]),
    ]
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, on_peak_id, True, {"start", "sum"}
    )
    assert stats[on_peak_id][0]["start"] == hour[3].timestamp()
    assert stats[on_peak_id][0]["sum"] == 4.0
    stats = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, off_peak_id, True, {"start", "sum"}
    )
    assert stats[off_peak_id][0]["start"] == hour[3].timestamp()
    assert stats[off_peak_id][0]["sum"] == 2.0


async def test_coordinator_rate_periods_added_after_totals(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test rate periods that appear once the totals already have statistics.

    This is the upgrade case: the totals continue from their stored statistic
    at the first refetched read and skip that read, but the new period
    statistics must include it.
    """
    hour = [dt_util.as_utc(datetime(2023, 1, 1, 8 + i)) for i in range(3)]

    # First run: reads without components, so only the totals are stored
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=hour[0], end_time=hour[1], consumption=1.0, provided_cost=0.5
        ),
        CostRead(
            start_time=hour[1], end_time=hour[2], consumption=2.0, provided_cost=1.0
        ),
    ]
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Second run: the same reads now carry components, plus a new read
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=hour[0],
            end_time=hour[1],
            consumption=1.0,
            provided_cost=0.5,
            read_components=[_read_component("ON_PEAK", 1.0, 0.5)],
        ),
        CostRead(
            start_time=hour[1],
            end_time=hour[2],
            consumption=2.0,
            provided_cost=1.0,
            read_components=[_read_component("ON_PEAK", 2.0, 1.0)],
        ),
        CostRead(
            start_time=hour[2],
            end_time=hour[2] + timedelta(hours=1),
            consumption=4.0,
            provided_cost=2.0,
            read_components=[_read_component("ON_PEAK", 4.0, 2.0)],
        ),
    ]
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {
            "opower:pge_elec_111111_energy_consumption",
            "opower:pge_elec_111111_on_peak_energy_consumption",
            "opower:pge_elec_111111_on_peak_energy_cost",
        },
        "hour",
        None,
        {"state", "sum"},
    )
    # The totals are unchanged for the first read and continue from there
    assert [s["sum"] for s in stats["opower:pge_elec_111111_energy_consumption"]] == [
        1.0,
        3.0,
        7.0,
    ]
    # The new period series starts at the first read, not the second
    assert [
        s["start"] for s in stats["opower:pge_elec_111111_on_peak_energy_consumption"]
    ] == [
        hour[0].timestamp(),
        hour[1].timestamp(),
        hour[2].timestamp(),
    ]
    assert [
        s["sum"] for s in stats["opower:pge_elec_111111_on_peak_energy_consumption"]
    ] == [
        1.0,
        3.0,
        7.0,
    ]
    assert [s["sum"] for s in stats["opower:pge_elec_111111_on_peak_energy_cost"]] == [
        0.5,
        1.5,
        3.5,
    ]
