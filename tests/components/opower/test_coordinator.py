"""Tests for the Opower coordinator."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from opower import AggregateType, CostRead, ReadResolution
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


async def test_coordinator_api_exceptions(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test the coordinator handles API exceptions."""
    coordinator = OpowerCoordinator(hass, mock_config_entry)

    # Error getting accounts
    mock_opower_api.async_get_accounts.side_effect = ApiException(
        "Error getting accounts", "http://example.com"
    )
    with pytest.raises(ApiException):
        await coordinator._async_update_data()
    mock_opower_api.async_get_accounts.side_effect = None

    # Error getting forecasts
    mock_opower_api.async_get_forecast.side_effect = ApiException(
        "Error getting forecasts", "http://example.com"
    )
    with pytest.raises(ApiException):
        await coordinator._async_update_data()
    mock_opower_api.async_get_forecast.side_effect = None

    # Error getting cost reads (monthly)
    mock_opower_api.async_get_cost_reads.side_effect = ApiException(
        "Error getting monthly cost reads", "http://example.com"
    )
    with pytest.raises(ApiException):
        await coordinator._async_update_data()
    mock_opower_api.async_get_cost_reads.side_effect = None


async def test_coordinator_finer_cost_reads_coverage(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test _update_with_finer_cost_reads coverage."""
    coordinator = OpowerCoordinator(hass, mock_config_entry)

    # Mock accounts to return only one account to simplify
    account = mock_opower_api.async_get_accounts.return_value[0]
    mock_opower_api.async_get_accounts.return_value = [account]

    t1 = dt_util.as_utc(datetime(2023, 1, 1, 0))
    t2 = dt_util.as_utc(datetime(2023, 1, 2, 0))
    t3 = dt_util.as_utc(datetime(2023, 1, 3, 0))

    def mock_get_cost_reads(acc, aggregate_type, start, end):
        if aggregate_type == AggregateType.BILL:
            return [
                CostRead(
                    start_time=t1, end_time=t2, consumption=10.0, provided_cost=2.0
                ),
                CostRead(
                    start_time=t2, end_time=t3, consumption=10.0, provided_cost=2.0
                ),
            ]
        if aggregate_type == AggregateType.DAY:
            # finer_cost_read.start_time == cost_read.start_time (t1)
            return [
                CostRead(
                    start_time=t1,
                    end_time=t1 + timedelta(hours=12),
                    consumption=5.0,
                    provided_cost=1.0,
                ),
            ]
        if aggregate_type == AggregateType.HOUR:
            # finer_cost_read.start_time == cost_read.end_time (t1 + 12h)
            return [
                CostRead(
                    start_time=t1 + timedelta(hours=12),
                    end_time=t1 + timedelta(hours=13),
                    consumption=1.0,
                    provided_cost=0.2,
                ),
            ]
        return []

    mock_opower_api.async_get_cost_reads.side_effect = mock_get_cost_reads

    await coordinator._async_update_data()


async def test_coordinator_migration_no_stats(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test _async_maybe_migrate_statistics when source_stats is empty."""
    statistic_id = "opower:pge_elec_111111_energy_consumption"
    target_id = "opower:pge_elec_111111_energy_return"

    coordinator = OpowerCoordinator(hass, mock_config_entry)

    migrated = await coordinator._async_maybe_migrate_statistics(
        "111111",
        {statistic_id: target_id},
        {
            statistic_id: StatisticMetaData(
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
                name="consumption",
                source=DOMAIN,
                statistic_id=statistic_id,
                unit_class=EnergyConverter.UNIT_CLASS,
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            ),
            target_id: StatisticMetaData(
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
                name="return",
                source=DOMAIN,
                statistic_id=target_id,
                unit_class=EnergyConverter.UNIT_CLASS,
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            ),
        },
    )
    # It returns True because an issue is created at the end
    assert migrated is True

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "return_to_grid_migration_111111")
    assert issue is not None


async def test_coordinator_more_api_exceptions(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test more API exceptions in _async_get_cost_reads."""
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    account = mock_opower_api.async_get_accounts.return_value[0]
    mock_opower_api.async_get_accounts.return_value = [account]

    async def mock_get_cost_reads(acc, aggregate_type, start, end):
        if aggregate_type == AggregateType.BILL:
            return [
                CostRead(
                    start_time=dt_util.utcnow(),
                    end_time=dt_util.utcnow(),
                    consumption=1.0,
                    provided_cost=0.1,
                )
            ]
        if aggregate_type == AggregateType.DAY:
            raise ApiException("Error getting daily cost reads", "http://example.com")
        return []

    mock_opower_api.async_get_cost_reads.side_effect = mock_get_cost_reads
    with pytest.raises(ApiException):
        await coordinator._async_update_data()

    async def mock_get_cost_reads_hourly(acc, aggregate_type, start, end):
        if aggregate_type == AggregateType.BILL:
            return [
                CostRead(
                    start_time=dt_util.utcnow(),
                    end_time=dt_util.utcnow(),
                    consumption=1.0,
                    provided_cost=0.1,
                )
            ]
        if aggregate_type == AggregateType.DAY:
            return []
        if aggregate_type == AggregateType.HOUR:
            raise ApiException("Error getting hourly cost reads", "http://example.com")
        return []

    mock_opower_api.async_get_cost_reads.side_effect = mock_get_cost_reads_hourly
    with pytest.raises(ApiException):
        await coordinator._async_update_data()


async def test_coordinator_migration_negative_state(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test migration logic with negative state to cover line 434."""
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
            start=dt_util.as_utc(datetime(2023, 1, 1, 8)), state=1.5, sum=1.5
        ),
        StatisticData(
            start=dt_util.as_utc(datetime(2023, 1, 1, 9)), state=-0.5, sum=1.0
        ),
    ]
    async_add_external_statistics(hass, metadata, statistics_to_add)
    await async_wait_recording_done(hass)

    mock_opower_api.async_get_cost_reads.return_value = []
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)
    # This covers line 434: new_target_state = max(0, -state) when state is negative


async def test_coordinator_update_data_api_exceptions(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test API exceptions in _async_update_data."""
    coordinator = OpowerCoordinator(hass, mock_config_entry)

    # Error getting accounts
    mock_opower_api.async_get_accounts.side_effect = ApiException(
        "Error", "http://example.com"
    )
    with pytest.raises(ApiException):
        await coordinator._async_update_data()
    mock_opower_api.async_get_accounts.side_effect = None

    # Error getting forecasts
    mock_opower_api.async_get_forecast.side_effect = ApiException(
        "Error", "http://example.com"
    )
    with pytest.raises(ApiException):
        await coordinator._async_update_data()
    mock_opower_api.async_get_forecast.side_effect = None


async def test_coordinator_get_cost_reads_api_exception(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test ApiException in _async_get_cost_reads during daily/hourly reads."""
    coordinator = OpowerCoordinator(hass, mock_config_entry)
    account = mock_opower_api.async_get_accounts.return_value[0]
    account.read_resolution = ReadResolution.HOUR
    mock_opower_api.async_get_accounts.return_value = [account]

    async def mock_get_cost_reads(acc, aggregate_type, start, end):
        if aggregate_type == AggregateType.BILL:
            return [
                CostRead(
                    start_time=dt_util.utcnow() - timedelta(days=60),
                    end_time=dt_util.utcnow() - timedelta(days=30),
                    consumption=1.0,
                    provided_cost=0.1,
                )
            ]
        if aggregate_type == AggregateType.DAY:
            raise ApiException("Error", "http://example.com")
        return []

    mock_opower_api.async_get_cost_reads.side_effect = mock_get_cost_reads
    with pytest.raises(ApiException):
        await coordinator._async_update_data()


async def test_coordinator_migration_empty_source_stats(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test _async_maybe_migrate_statistics with empty source stats to cover line 400."""
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
    assert migrated is True
