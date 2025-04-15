"""The tests for sensor recorder platform."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import ANY, Mock, patch

import pytest
from sqlalchemy import select

from homeassistant.components import recorder
from homeassistant.components.recorder import Recorder, history, statistics
from homeassistant.components.recorder.db_schema import StatisticsShortTerm
from homeassistant.components.recorder.models import (
    StatisticMeanType,
    datetime_to_timestamp_or_none,
    process_timestamp,
)
from homeassistant.components.recorder.statistics import (
    STATISTIC_UNIT_TO_UNIT_CONVERTER,
    PlatformCompiledStatistics,
    _generate_max_mean_min_statistic_in_sub_period_stmt,
    _generate_statistics_at_time_stmt_dependent_sub_query,
    _generate_statistics_at_time_stmt_group_by,
    _generate_statistics_during_period_stmt,
    async_add_external_statistics,
    async_import_statistics,
    async_list_statistic_ids,
    get_last_short_term_statistics,
    get_last_statistics,
    get_latest_short_term_statistics_with_session,
    get_metadata,
    get_metadata_with_session,
    get_short_term_statistics_run_cache,
    list_statistic_ids,
    validate_statistics,
)
from homeassistant.components.recorder.table_managers.statistics_meta import (
    _generate_get_metadata_stmt,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.sensor import UNIT_CONVERTERS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import (
    assert_dict_of_states_equal_without_context_and_last_changed,
    async_record_states,
    async_recorder_block_till_done,
    async_wait_recording_done,
    do_adhoc_statistics,
    get_start_time,
    statistics_during_period,
)

from tests.common import MockPlatform, mock_platform
from tests.typing import RecorderInstanceContextManager, WebSocketGenerator


@pytest.fixture
def multiple_start_time_chunk_sizes(
    ids_for_start_time_chunk_sizes: int,
) -> Generator[None]:
    """Fixture to test different chunk sizes for start time query.

    Force the statistics query to use different chunk sizes for start time query.

    In effect this forces _statistics_at_time
    to call _generate_statistics_at_time_stmt_group_by multiple times.
    """
    with patch(
        "homeassistant.components.recorder.statistics.MAX_IDS_FOR_INDEXED_GROUP_BY",
        ids_for_start_time_chunk_sizes,
    ):
        yield


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


@pytest.fixture
def setup_recorder(recorder_mock: Recorder) -> None:
    """Set up recorder."""


async def _setup_mock_domain(
    hass: HomeAssistant,
    platform: Any | None = None,  # There's no RecorderPlatform class yet
) -> None:
    """Set up a mock domain."""
    mock_platform(hass, "some_domain.recorder", platform or MockPlatform())
    assert await async_setup_component(hass, "some_domain", {})


def test_converters_align_with_sensor() -> None:
    """Ensure STATISTIC_UNIT_TO_UNIT_CONVERTER is aligned with UNIT_CONVERTERS."""
    for converter in UNIT_CONVERTERS.values():
        assert converter in STATISTIC_UNIT_TO_UNIT_CONVERTER.values()

    for converter in STATISTIC_UNIT_TO_UNIT_CONVERTER.values():
        assert converter in UNIT_CONVERTERS.values()


async def test_compile_hourly_statistics(
    hass: HomeAssistant,
    setup_recorder: None,
) -> None:
    """Test compiling hourly statistics."""
    instance = recorder.get_instance(hass)
    await async_setup_component(hass, "sensor", {})
    zero, four, states = await async_record_states(hass)
    hist = history.get_significant_states(hass, zero, four, list(states))
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    # Should not fail if there is nothing there yet
    with session_scope(hass=hass, read_only=True) as session:
        stats = get_latest_short_term_statistics_with_session(
            hass,
            session,
            {"sensor.test1", "sensor.wind_direction"},
            {"last_reset", "max", "mean", "min", "state", "sum"},
        )
    assert stats == {}

    for kwargs in ({}, {"statistic_ids": ["sensor.test1", "sensor.wind_direction"]}):
        stats = statistics_during_period(hass, zero, period="5minute", **kwargs)
        assert stats == {}
    for sensor in ("sensor.test1", "sensor.wind_direction"):
        stats = get_last_short_term_statistics(
            hass,
            0,
            sensor,
            True,
            {"last_reset", "max", "mean", "min", "state", "sum"},
        )
        assert stats == {}

    do_adhoc_statistics(hass, start=zero)
    do_adhoc_statistics(hass, start=four)
    await async_wait_recording_done(hass)

    metadata = get_metadata(
        hass, statistic_ids={"sensor.test1", "sensor.test2", "sensor.wind_direction"}
    )
    for sensor, mean_type in (
        ("sensor.test1", StatisticMeanType.ARITHMETIC),
        ("sensor.test2", StatisticMeanType.ARITHMETIC),
        ("sensor.wind_direction", StatisticMeanType.CIRCULAR),
    ):
        assert metadata[sensor][1]["mean_type"] is mean_type
        assert metadata[sensor][1]["has_sum"] is False
    expected_1 = {
        "start": process_timestamp(zero).timestamp(),
        "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
        "mean": pytest.approx(14.915254237288135),
        "min": pytest.approx(10.0),
        "max": pytest.approx(20.0),
        "last_reset": None,
    }
    expected_2 = {
        "start": process_timestamp(four).timestamp(),
        "end": process_timestamp(four + timedelta(minutes=5)).timestamp(),
        "mean": pytest.approx(20.0),
        "min": pytest.approx(20.0),
        "max": pytest.approx(20.0),
        "last_reset": None,
    }
    expected_stats1 = [expected_1, expected_2]
    expected_stats2 = [expected_1, expected_2]

    expected_stats_wind_direction1 = {
        "start": process_timestamp(zero).timestamp(),
        "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
        "mean": pytest.approx(358.6387003873801),
        "min": None,
        "max": None,
        "last_reset": None,
    }
    expected_stats_wind_direction2 = {
        "start": process_timestamp(four).timestamp(),
        "end": process_timestamp(four + timedelta(minutes=5)).timestamp(),
        "mean": pytest.approx(5),
        "min": None,
        "max": None,
        "last_reset": None,
    }
    expected_stats_wind_direction = [
        expected_stats_wind_direction1,
        expected_stats_wind_direction2,
    ]

    # Test statistics_during_period
    stats = statistics_during_period(
        hass,
        zero,
        period="5minute",
        statistic_ids={"sensor.test1", "sensor.test2", "sensor.wind_direction"},
    )
    assert stats == {
        "sensor.test1": expected_stats1,
        "sensor.test2": expected_stats2,
        "sensor.wind_direction": expected_stats_wind_direction,
    }

    # Test statistics_during_period with a far future start and end date
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(
        hass,
        future,
        end_time=future,
        period="5minute",
        statistic_ids={"sensor.test1", "sensor.test2", "sensor.wind_direction"},
    )
    assert stats == {}

    # Test statistics_during_period with a far future end date
    stats = statistics_during_period(
        hass,
        zero,
        end_time=future,
        period="5minute",
        statistic_ids={"sensor.test1", "sensor.test2", "sensor.wind_direction"},
    )
    assert stats == {
        "sensor.test1": expected_stats1,
        "sensor.test2": expected_stats2,
        "sensor.wind_direction": expected_stats_wind_direction,
    }

    stats = statistics_during_period(
        hass, zero, statistic_ids={"sensor.test2"}, period="5minute"
    )
    assert stats == {"sensor.test2": expected_stats2}

    stats = statistics_during_period(
        hass, zero, statistic_ids={"sensor.test3"}, period="5minute"
    )
    assert stats == {}

    # Test get_last_short_term_statistics and get_latest_short_term_statistics
    for sensor, expected in (
        ("sensor.test1", expected_2),
        ("sensor.wind_direction", expected_stats_wind_direction2),
    ):
        stats = get_last_short_term_statistics(
            hass,
            0,
            sensor,
            True,
            {"last_reset", "max", "mean", "min", "state", "sum"},
        )
        assert stats == {}

        stats = get_last_short_term_statistics(
            hass,
            1,
            sensor,
            True,
            {"last_reset", "max", "mean", "min", "state", "sum"},
        )
        assert stats == {sensor: [expected]}

    with session_scope(hass=hass, read_only=True) as session:
        stats = get_latest_short_term_statistics_with_session(
            hass,
            session,
            {"sensor.test1", "sensor.wind_direction"},
            {"last_reset", "max", "mean", "min", "state", "sum"},
        )
    assert stats == {
        "sensor.test1": [expected_2],
        "sensor.wind_direction": [expected_stats_wind_direction2],
    }

    # Now wipe the latest_short_term_statistics_ids table and test again
    # to make sure we can rebuild the missing data
    run_cache = get_short_term_statistics_run_cache(instance.hass)
    run_cache._latest_id_by_metadata_id = {}
    with session_scope(hass=hass, read_only=True) as session:
        stats = get_latest_short_term_statistics_with_session(
            hass,
            session,
            {"sensor.test1", "sensor.wind_direction"},
            {"last_reset", "max", "mean", "min", "state", "sum"},
        )
    assert stats == {
        "sensor.test1": [expected_2],
        "sensor.wind_direction": [expected_stats_wind_direction2],
    }

    metadata = get_metadata(hass, statistic_ids={"sensor.test1"})
    with session_scope(hass=hass, read_only=True) as session:
        stats = get_latest_short_term_statistics_with_session(
            hass,
            session,
            {"sensor.test1"},
            {"last_reset", "max", "mean", "min", "state", "sum"},
            metadata=metadata,
        )
    assert stats == {"sensor.test1": [expected_2]}

    # Test with multiple metadata ids
    metadata = get_metadata(
        hass, statistic_ids={"sensor.test1", "sensor.wind_direction"}
    )
    with session_scope(hass=hass, read_only=True) as session:
        stats = get_latest_short_term_statistics_with_session(
            hass,
            session,
            {"sensor.test1", "sensor.wind_direction"},
            {"last_reset", "max", "mean", "min", "state", "sum"},
            metadata=metadata,
        )
    assert stats == {
        "sensor.test1": [expected_2],
        "sensor.wind_direction": [expected_stats_wind_direction2],
    }

    for sensor, expected in (
        ("sensor.test1", expected_stats1[::-1]),
        ("sensor.wind_direction", expected_stats_wind_direction[::-1]),
    ):
        stats = get_last_short_term_statistics(
            hass,
            2,
            sensor,
            True,
            {"last_reset", "max", "mean", "min", "state", "sum"},
        )
        assert stats == {sensor: expected}

        stats = get_last_short_term_statistics(
            hass,
            3,
            sensor,
            True,
            {"last_reset", "max", "mean", "min", "state", "sum"},
        )
        assert stats == {sensor: expected}

    stats = get_last_short_term_statistics(
        hass,
        1,
        "sensor.test3",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {}

    instance.get_session().query(StatisticsShortTerm).delete()
    # Should not fail there is nothing in the table
    with session_scope(hass=hass, read_only=True) as session:
        stats = get_latest_short_term_statistics_with_session(
            hass,
            session,
            {"sensor.test1", "sensor.wind_direction"},
            {"last_reset", "max", "mean", "min", "state", "sum"},
        )
        assert stats == {}

    # Delete again, and manually wipe the cache since we deleted all the data
    instance.get_session().query(StatisticsShortTerm).delete()
    run_cache = get_short_term_statistics_run_cache(instance.hass)
    run_cache._latest_id_by_metadata_id = {}

    # And test again to make sure there is no data
    with session_scope(hass=hass, read_only=True) as session:
        stats = get_latest_short_term_statistics_with_session(
            hass,
            session,
            {"sensor.test1", "sensor.wind_direction"},
            {"last_reset", "max", "mean", "min", "state", "sum"},
        )
    assert stats == {}


@pytest.fixture
def mock_sensor_statistics():
    """Generate some fake statistics."""

    def sensor_stats(entity_id, start):
        """Generate fake statistics."""
        return {
            "meta": {
                "has_mean": True,
                "has_sum": False,
                "name": None,
                "statistic_id": entity_id,
                "unit_of_measurement": "dogs",
            },
            "stat": {"start": start},
        }

    def get_fake_stats(_hass, session, start, _end):
        instance = recorder.get_instance(_hass)
        return statistics.PlatformCompiledStatistics(
            [
                sensor_stats("sensor.test1", start),
                sensor_stats("sensor.test2", start),
                sensor_stats("sensor.test3", start),
            ],
            get_metadata_with_session(
                instance,
                session,
                statistic_ids={"sensor.test1", "sensor.test2", "sensor.test3"},
            ),
        )

    with patch(
        "homeassistant.components.sensor.recorder.compile_statistics",
        side_effect=get_fake_stats,
    ):
        yield


@pytest.fixture
def mock_from_stats():
    """Mock out Statistics.from_stats."""
    counter = 0
    real_from_stats = StatisticsShortTerm.from_stats

    def from_stats(metadata_id, stats, now_timestamp):
        nonlocal counter
        if counter == 0 and metadata_id == 2:
            counter += 1
            return None
        return real_from_stats(metadata_id, stats, now_timestamp)

    with patch(
        "homeassistant.components.recorder.statistics.StatisticsShortTerm.from_stats",
        side_effect=from_stats,
        autospec=True,
    ):
        yield


async def test_compile_periodic_statistics_exception(
    hass: HomeAssistant, setup_recorder: None, mock_sensor_statistics, mock_from_stats
) -> None:
    """Test exception handling when compiling periodic statistics."""
    await async_setup_component(hass, "sensor", {})

    now = get_start_time(dt_util.utcnow())
    do_adhoc_statistics(hass, start=now)
    do_adhoc_statistics(hass, start=now + timedelta(minutes=5))
    await async_wait_recording_done(hass)
    expected_1 = {
        "start": process_timestamp(now).timestamp(),
        "end": process_timestamp(now + timedelta(minutes=5)).timestamp(),
        "mean": None,
        "min": None,
        "max": None,
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_2 = {
        "start": process_timestamp(now + timedelta(minutes=5)).timestamp(),
        "end": process_timestamp(now + timedelta(minutes=10)).timestamp(),
        "mean": None,
        "min": None,
        "max": None,
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_stats1 = [expected_1, expected_2]
    expected_stats2 = [expected_2]
    expected_stats3 = [expected_1, expected_2]

    stats = statistics_during_period(hass, now, period="5minute")
    assert stats == {
        "sensor.test1": expected_stats1,
        "sensor.test2": expected_stats2,
        "sensor.test3": expected_stats3,
    }


async def test_rename_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_recorder: None
) -> None:
    """Test statistics is migrated when entity_id is changed."""
    await async_setup_component(hass, "sensor", {})

    reg_entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_0000",
        suggested_object_id="test1",
    )
    assert reg_entry.entity_id == "sensor.test1"
    await hass.async_block_till_done()

    zero, four, states = await async_record_states(hass)
    hist = history.get_significant_states(hass, zero, four, list(states))
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    for kwargs in ({}, {"statistic_ids": ["sensor.test1"]}):
        stats = statistics_during_period(hass, zero, period="5minute", **kwargs)
        assert stats == {}
    stats = get_last_short_term_statistics(
        hass,
        0,
        "sensor.test1",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {}

    do_adhoc_statistics(hass, start=zero)
    await async_wait_recording_done(hass)
    expected_1 = {
        "start": process_timestamp(zero).timestamp(),
        "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
        "mean": pytest.approx(14.915254237288135),
        "min": pytest.approx(10.0),
        "max": pytest.approx(20.0),
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_stats1 = [expected_1]
    expected_stats2 = [expected_1]
    expected_stats99 = [expected_1]
    expected_stats_wind_direction = [
        {
            "start": process_timestamp(zero).timestamp(),
            "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
            "mean": pytest.approx(358.6387003873801),
            "min": None,
            "max": None,
            "last_reset": None,
            "state": None,
            "sum": None,
        }
    ]

    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": expected_stats1,
        "sensor.test2": expected_stats2,
        "sensor.wind_direction": expected_stats_wind_direction,
    }

    entity_registry.async_update_entity("sensor.test1", new_entity_id="sensor.test99")
    await async_wait_recording_done(hass)

    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test99": expected_stats99,
        "sensor.test2": expected_stats2,
        "sensor.wind_direction": expected_stats_wind_direction,
    }


async def test_statistics_during_period_set_back_compat(
    hass: HomeAssistant,
    setup_recorder: None,
) -> None:
    """Test statistics_during_period can handle a list instead of a set."""
    await async_setup_component(hass, "sensor", {})
    # This should not throw an exception when passed a list instead of a set
    assert (
        statistics.statistics_during_period(
            hass,
            dt_util.utcnow(),
            None,
            statistic_ids=["sensor.test1"],
            period="5minute",
            units=None,
            types=set(),
        )
        == {}
    )


async def test_rename_entity_collision(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test statistics is migrated when entity_id is changed.

    This test relies on the safeguard in the statistics_meta_manager
    and should not hit the filter_unique_constraint_integrity_error safeguard.
    """
    await async_setup_component(hass, "sensor", {})

    reg_entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_0000",
        suggested_object_id="test1",
    )
    assert reg_entry.entity_id == "sensor.test1"
    await hass.async_block_till_done()

    zero, four, states = await async_record_states(hass)
    hist = history.get_significant_states(hass, zero, four, list(states))
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    for kwargs in ({}, {"statistic_ids": ["sensor.test1"]}):
        stats = statistics_during_period(hass, zero, period="5minute", **kwargs)
        assert stats == {}
    stats = get_last_short_term_statistics(
        hass,
        0,
        "sensor.test1",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {}

    do_adhoc_statistics(hass, start=zero)
    await async_wait_recording_done(hass)
    expected_1 = {
        "start": process_timestamp(zero).timestamp(),
        "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
        "mean": pytest.approx(14.915254237288135),
        "min": pytest.approx(10.0),
        "max": pytest.approx(20.0),
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_stats1 = [expected_1]
    expected_stats2 = [expected_1]
    expected_stats_wind_direction = [
        {
            "start": process_timestamp(zero).timestamp(),
            "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
            "mean": pytest.approx(358.6387003873801),
            "min": None,
            "max": None,
            "last_reset": None,
            "state": None,
            "sum": None,
        }
    ]

    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": expected_stats1,
        "sensor.test2": expected_stats2,
        "sensor.wind_direction": expected_stats_wind_direction,
    }

    # Insert metadata for sensor.test99
    metadata_1 = {
        "has_mean": True,
        "has_sum": False,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "sensor.test99",
        "unit_of_measurement": "kWh",
    }

    with session_scope(hass=hass) as session:
        session.add(recorder.db_schema.StatisticsMeta.from_meta(metadata_1))

    # Rename entity sensor.test1 to sensor.test99
    entity_registry.async_update_entity("sensor.test1", new_entity_id="sensor.test99")
    await async_wait_recording_done(hass)

    # Statistics failed to migrate due to the collision
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": expected_stats1,
        "sensor.test2": expected_stats2,
        "sensor.wind_direction": expected_stats_wind_direction,
    }

    # Verify the safeguard in the states meta manager was hit
    assert (
        "Cannot rename statistic_id `sensor.test1` to `sensor.test99` "
        "because the new statistic_id is already in use"
    ) in caplog.text

    # Verify the filter_unique_constraint_integrity_error safeguard was not hit
    assert "Blocked attempt to insert duplicated statistic rows" not in caplog.text


async def test_rename_entity_collision_states_meta_check_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test statistics is migrated when entity_id is changed.

    This test disables the safeguard in the statistics_meta_manager
    and relies on the filter_unique_constraint_integrity_error safeguard.
    """
    await async_setup_component(hass, "sensor", {})

    reg_entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_0000",
        suggested_object_id="test1",
    )
    assert reg_entry.entity_id == "sensor.test1"
    await hass.async_block_till_done()

    zero, four, states = await async_record_states(hass)
    hist = history.get_significant_states(hass, zero, four, list(states))
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    for kwargs in ({}, {"statistic_ids": ["sensor.test1"]}):
        stats = statistics_during_period(hass, zero, period="5minute", **kwargs)
        assert stats == {}
    stats = get_last_short_term_statistics(
        hass,
        0,
        "sensor.test1",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {}

    do_adhoc_statistics(hass, start=zero)
    await async_wait_recording_done(hass)
    expected_1 = {
        "start": process_timestamp(zero).timestamp(),
        "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
        "mean": pytest.approx(14.915254237288135),
        "min": pytest.approx(10.0),
        "max": pytest.approx(20.0),
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_stats1 = [expected_1]
    expected_stats2 = [expected_1]
    expected_stats_wind_direction = [
        {
            "start": process_timestamp(zero).timestamp(),
            "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
            "mean": pytest.approx(358.6387003873801),
            "min": None,
            "max": None,
            "last_reset": None,
            "state": None,
            "sum": None,
        }
    ]

    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": expected_stats1,
        "sensor.test2": expected_stats2,
        "sensor.wind_direction": expected_stats_wind_direction,
    }

    # Insert metadata for sensor.test99
    metadata_1 = {
        "has_mean": True,
        "has_sum": False,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "sensor.test99",
        "unit_of_measurement": "kWh",
    }

    with session_scope(hass=hass) as session:
        session.add(recorder.db_schema.StatisticsMeta.from_meta(metadata_1))

    instance = recorder.get_instance(hass)
    # Patch out the safeguard in the states meta manager
    # so that we hit the filter_unique_constraint_integrity_error safeguard in the statistics
    with patch.object(instance.statistics_meta_manager, "get", return_value=None):
        # Rename entity sensor.test1 to sensor.test99
        entity_registry.async_update_entity(
            "sensor.test1", new_entity_id="sensor.test99"
        )
        await async_wait_recording_done(hass)

    # Statistics failed to migrate due to the collision
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": expected_stats1,
        "sensor.test2": expected_stats2,
        "sensor.wind_direction": expected_stats_wind_direction,
    }

    # Verify the filter_unique_constraint_integrity_error safeguard was hit
    assert "Blocked attempt to insert duplicated statistic rows" in caplog.text

    # Verify the safeguard in the states meta manager was not hit
    assert (
        "Cannot rename statistic_id `sensor.test1` to `sensor.test99` "
        "because the new statistic_id is already in use"
    ) not in caplog.text


async def test_statistics_duplicated(
    hass: HomeAssistant, setup_recorder: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Test statistics with same start time is not compiled."""
    await async_setup_component(hass, "sensor", {})
    zero, four, states = await async_record_states(hass)
    hist = history.get_significant_states(hass, zero, four, list(states))
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    await async_wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    with patch(
        "homeassistant.components.sensor.recorder.compile_statistics",
        return_value=statistics.PlatformCompiledStatistics([], {}),
    ) as compile_statistics:
        do_adhoc_statistics(hass, start=zero)
        await async_wait_recording_done(hass)
        assert compile_statistics.called
        compile_statistics.reset_mock()
        assert "Compiling statistics for" in caplog.text
        assert "Statistics already compiled" not in caplog.text
        caplog.clear()

        do_adhoc_statistics(hass, start=zero)
        await async_wait_recording_done(hass)
        assert not compile_statistics.called
        compile_statistics.reset_mock()
        assert "Compiling statistics for" not in caplog.text
        assert "Statistics already compiled" in caplog.text
        caplog.clear()


@pytest.mark.parametrize("last_reset_str", ["2022-01-01T00:00:00+02:00", None])
@pytest.mark.parametrize(
    ("source", "statistic_id", "import_fn"),
    [
        ("test", "test:total_energy_import", async_add_external_statistics),
        ("recorder", "sensor.total_energy_import", async_import_statistics),
    ],
)
async def test_import_statistics(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    source,
    statistic_id,
    import_fn,
    last_reset_str,
) -> None:
    """Test importing statistics and inserting external statistics."""
    client = await hass_ws_client()

    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    last_reset = dt_util.parse_datetime(last_reset_str) if last_reset_str else None
    last_reset_utc = dt_util.as_utc(last_reset) if last_reset else None
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    period2 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    external_statistics1 = {
        "start": period1,
        "last_reset": last_reset,
        "state": 0,
        "sum": 2,
    }
    external_statistics2 = {
        "start": period2,
        "last_reset": last_reset,
        "state": 1,
        "sum": 3,
    }

    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": source,
        "statistic_id": statistic_id,
        "unit_of_measurement": "kWh",
    }

    import_fn(hass, external_metadata, (external_statistics1, external_statistics2))
    await async_wait_recording_done(hass)
    stats = statistics_during_period(
        hass, zero, period="hour", statistic_ids={statistic_id}
    )
    assert stats == {
        statistic_id: [
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1 + timedelta(hours=1)).timestamp(),
                "last_reset": datetime_to_timestamp_or_none(last_reset_utc),
                "state": pytest.approx(0.0),
                "sum": pytest.approx(2.0),
            },
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2 + timedelta(hours=1)).timestamp(),
                "last_reset": datetime_to_timestamp_or_none(last_reset_utc),
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
            "statistic_id": statistic_id,
            "name": "Total imported energy",
            "source": source,
            "statistics_unit_of_measurement": "kWh",
            "unit_class": "energy",
        }
    ]
    metadata = get_metadata(hass, statistic_ids={statistic_id})
    assert metadata == {
        statistic_id: (
            1,
            {
                "has_mean": False,
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
                "name": "Total imported energy",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": "kWh",
            },
        )
    }
    last_stats = get_last_statistics(
        hass,
        1,
        statistic_id,
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert last_stats == {
        statistic_id: [
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2 + timedelta(hours=1)).timestamp(),
                "last_reset": datetime_to_timestamp_or_none(last_reset_utc),
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }

    # Update the previously inserted statistics
    external_statistics = {
        "start": period1,
        "last_reset": None,
        "state": 5,
        "sum": 6,
    }
    import_fn(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    stats = statistics_during_period(
        hass, zero, period="hour", statistic_ids={statistic_id}
    )
    assert stats == {
        statistic_id: [
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1 + timedelta(hours=1)).timestamp(),
                "last_reset": None,
                "state": pytest.approx(5.0),
                "sum": pytest.approx(6.0),
            },
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2 + timedelta(hours=1)).timestamp(),
                "last_reset": datetime_to_timestamp_or_none(last_reset_utc),
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }

    # Update the previously inserted statistics + rename
    external_statistics = {
        "start": period1,
        "max": 1,
        "mean": 2,
        "min": 3,
        "last_reset": last_reset,
        "state": 4,
        "sum": 5,
    }
    external_metadata["name"] = "Total imported energy renamed"
    import_fn(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
            "statistic_id": statistic_id,
            "name": "Total imported energy renamed",
            "source": source,
            "statistics_unit_of_measurement": "kWh",
            "unit_class": "energy",
        }
    ]
    metadata = get_metadata(hass, statistic_ids={statistic_id})
    assert metadata == {
        statistic_id: (
            1,
            {
                "has_mean": False,
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
                "name": "Total imported energy renamed",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": "kWh",
            },
        )
    }
    stats = statistics_during_period(
        hass, zero, period="hour", statistic_ids={statistic_id}
    )
    assert stats == {
        statistic_id: [
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1 + timedelta(hours=1)).timestamp(),
                "last_reset": datetime_to_timestamp_or_none(last_reset_utc),
                "state": pytest.approx(4.0),
                "sum": pytest.approx(5.0),
            },
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2 + timedelta(hours=1)).timestamp(),
                "last_reset": datetime_to_timestamp_or_none(last_reset_utc),
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }

    # Adjust the statistics in a different unit
    await client.send_json_auto_id(
        {
            "type": "recorder/adjust_sum_statistics",
            "statistic_id": statistic_id,
            "start_time": period2.isoformat(),
            "adjustment": 1000.0,
            "adjustment_unit_of_measurement": "MWh",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await async_wait_recording_done(hass)
    stats = statistics_during_period(
        hass, zero, period="hour", statistic_ids={statistic_id}
    )
    assert stats == {
        statistic_id: [
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1 + timedelta(hours=1)).timestamp(),
                "last_reset": datetime_to_timestamp_or_none(last_reset_utc),
                "state": pytest.approx(4.0),
                "sum": pytest.approx(5.0),
            },
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2 + timedelta(hours=1)).timestamp(),
                "last_reset": datetime_to_timestamp_or_none(last_reset_utc),
                "state": pytest.approx(1.0),
                "sum": pytest.approx(1000 * 1000 + 3.0),
            },
        ]
    }


async def test_external_statistics_errors(
    hass: HomeAssistant, setup_recorder: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Test validation of external statistics."""
    await async_wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    last_reset = zero.replace(minute=0, second=0, microsecond=0) - timedelta(days=1)
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    _external_statistics = {
        "start": period1,
        "last_reset": last_reset,
        "state": 0,
        "sum": 2,
    }

    _external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    # Attempt to insert statistics for an entity
    external_metadata = {
        **_external_metadata,
        "statistic_id": "sensor.total_energy_import",
    }
    external_statistics = {**_external_statistics}
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids={"sensor.total_energy_import"}) == {}

    # Attempt to insert statistics for the wrong domain
    external_metadata = {**_external_metadata, "source": "other"}
    external_statistics = {**_external_statistics}
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids={"test:total_energy_import"}) == {}

    # Attempt to insert statistics for a naive starting time
    external_metadata = {**_external_metadata}
    external_statistics = {
        **_external_statistics,
        "start": period1.replace(tzinfo=None),
    }
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids={"test:total_energy_import"}) == {}

    # Attempt to insert statistics for an invalid starting time
    external_metadata = {**_external_metadata}
    external_statistics = {**_external_statistics, "start": period1.replace(minute=1)}
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids={"test:total_energy_import"}) == {}

    # Attempt to insert statistics with a naive last_reset
    external_metadata = {**_external_metadata}
    external_statistics = {
        **_external_statistics,
        "last_reset": last_reset.replace(tzinfo=None),
    }
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids={"test:total_energy_import"}) == {}


async def test_import_statistics_errors(
    hass: HomeAssistant, setup_recorder: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Test validation of imported statistics."""
    await async_wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    last_reset = zero.replace(minute=0, second=0, microsecond=0) - timedelta(days=1)
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    _external_statistics = {
        "start": period1,
        "last_reset": last_reset,
        "state": 0,
        "sum": 2,
    }

    _external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "recorder",
        "statistic_id": "sensor.total_energy_import",
        "unit_of_measurement": "kWh",
    }

    # Attempt to insert statistics for an external source
    external_metadata = {
        **_external_metadata,
        "statistic_id": "test:total_energy_import",
    }
    external_statistics = {**_external_statistics}
    with pytest.raises(HomeAssistantError):
        async_import_statistics(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids={"test:total_energy_import"}) == {}

    # Attempt to insert statistics for the wrong domain
    external_metadata = {**_external_metadata, "source": "sensor"}
    external_statistics = {**_external_statistics}
    with pytest.raises(HomeAssistantError):
        async_import_statistics(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids={"sensor.total_energy_import"}) == {}

    # Attempt to insert statistics for a naive starting time
    external_metadata = {**_external_metadata}
    external_statistics = {
        **_external_statistics,
        "start": period1.replace(tzinfo=None),
    }
    with pytest.raises(HomeAssistantError):
        async_import_statistics(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids={"sensor.total_energy_import"}) == {}

    # Attempt to insert statistics for an invalid starting time
    external_metadata = {**_external_metadata}
    external_statistics = {**_external_statistics, "start": period1.replace(minute=1)}
    with pytest.raises(HomeAssistantError):
        async_import_statistics(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids={"sensor.total_energy_import"}) == {}

    # Attempt to insert statistics with a naive last_reset
    external_metadata = {**_external_metadata}
    external_statistics = {
        **_external_statistics,
        "last_reset": last_reset.replace(tzinfo=None),
    }
    with pytest.raises(HomeAssistantError):
        async_import_statistics(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids={"sensor.total_energy_import"}) == {}


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
@pytest.mark.parametrize("timezone", ["America/Regina", "Europe/Vienna", "UTC"])
@pytest.mark.freeze_time("2022-10-01 00:00:00+00:00")
async def test_daily_statistics_sum(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
    timezone,
) -> None:
    """Test daily statistics."""
    await hass.config.async_set_time_zone(timezone)
    await async_wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2022-10-04 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2022-10-04 23:00:00"))
    period5 = dt_util.as_utc(dt_util.parse_datetime("2022-10-05 00:00:00"))
    period6 = dt_util.as_utc(dt_util.parse_datetime("2022-10-05 23:00:00"))

    external_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 4,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 5,
        },
        {
            "start": period5,
            "last_reset": None,
            "state": 4,
            "sum": 6,
        },
        {
            "start": period6,
            "last_reset": None,
            "state": 5,
            "sum": 7,
        },
    )
    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(hass, external_metadata, external_statistics)
    await async_wait_recording_done(hass)
    stats = statistics_during_period(
        hass, zero, period="day", statistic_ids={"test:total_energy_import"}
    )
    day1_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 00:00:00"))
    day1_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-04 00:00:00"))
    day2_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-04 00:00:00"))
    day2_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-05 00:00:00"))
    day3_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-05 00:00:00"))
    day3_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-06 00:00:00"))
    expected_stats = {
        "test:total_energy_import": [
            {
                "start": day1_start.timestamp(),
                "end": day1_end.timestamp(),
                "last_reset": None,
                "state": 1.0,
                "sum": 3.0,
            },
            {
                "start": day2_start.timestamp(),
                "end": day2_end.timestamp(),
                "last_reset": None,
                "state": 3.0,
                "sum": 5.0,
            },
            {
                "start": day3_start.timestamp(),
                "end": day3_end.timestamp(),
                "last_reset": None,
                "state": 5.0,
                "sum": 7.0,
            },
        ]
    }
    assert stats == expected_stats

    # Get change
    stats = statistics_during_period(
        hass,
        start_time=period1,
        statistic_ids={"test:total_energy_import"},
        period="day",
        types={"change"},
    )
    assert stats == {
        "test:total_energy_import": [
            {
                "start": day1_start.timestamp(),
                "end": day1_end.timestamp(),
                "change": 3.0,
            },
            {
                "start": day2_start.timestamp(),
                "end": day2_end.timestamp(),
                "change": 2.0,
            },
            {
                "start": day3_start.timestamp(),
                "end": day3_end.timestamp(),
                "change": 2.0,
            },
        ]
    }

    # Get data with start during the first period
    stats = statistics_during_period(
        hass,
        start_time=period1 + timedelta(hours=1),
        statistic_ids={"test:total_energy_import"},
        period="day",
    )
    assert stats == expected_stats

    # Get data with end during the third period
    stats = statistics_during_period(
        hass,
        start_time=zero,
        end_time=period6 - timedelta(hours=1),
        statistic_ids={"test:total_energy_import"},
        period="day",
    )
    assert stats == expected_stats

    # Try to get data for entities which do not exist
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids={"not", "the", "same", "test:total_energy_import"},
        period="day",
    )
    assert stats == expected_stats

    # Use 5minute to ensure table switch works
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids=["test:total_energy_import", "with_other"],
        period="5minute",
    )
    assert stats == {}

    # Ensure future date has not data
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(
        hass, start_time=future, end_time=future, period="day"
    )
    assert stats == {}


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
@pytest.mark.parametrize("timezone", ["America/Regina", "Europe/Vienna", "UTC"])
@pytest.mark.freeze_time("2022-10-01 00:00:00+00:00")
async def test_multiple_daily_statistics_sum(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
    timezone,
) -> None:
    """Test daily statistics."""
    await hass.config.async_set_time_zone(timezone)
    await async_wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2022-10-04 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2022-10-04 23:00:00"))
    period5 = dt_util.as_utc(dt_util.parse_datetime("2022-10-05 00:00:00"))
    period6 = dt_util.as_utc(dt_util.parse_datetime("2022-10-05 23:00:00"))

    external_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 4,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 5,
        },
        {
            "start": period5,
            "last_reset": None,
            "state": 4,
            "sum": 6,
        },
        {
            "start": period6,
            "last_reset": None,
            "state": 5,
            "sum": 7,
        },
    )
    external_metadata1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy 1",
        "source": "test",
        "statistic_id": "test:total_energy_import2",
        "unit_of_measurement": "kWh",
    }
    external_metadata2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy 2",
        "source": "test",
        "statistic_id": "test:total_energy_import1",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(hass, external_metadata1, external_statistics)
    async_add_external_statistics(hass, external_metadata2, external_statistics)

    await async_wait_recording_done(hass)
    stats = statistics_during_period(
        hass,
        zero,
        period="day",
        statistic_ids={"test:total_energy_import1", "test:total_energy_import2"},
    )
    day1_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 00:00:00"))
    day1_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-04 00:00:00"))
    day2_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-04 00:00:00"))
    day2_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-05 00:00:00"))
    day3_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-05 00:00:00"))
    day3_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-06 00:00:00"))
    expected_stats_inner = [
        {
            "start": day1_start.timestamp(),
            "end": day1_end.timestamp(),
            "last_reset": None,
            "state": 1.0,
            "sum": 3.0,
        },
        {
            "start": day2_start.timestamp(),
            "end": day2_end.timestamp(),
            "last_reset": None,
            "state": 3.0,
            "sum": 5.0,
        },
        {
            "start": day3_start.timestamp(),
            "end": day3_end.timestamp(),
            "last_reset": None,
            "state": 5.0,
            "sum": 7.0,
        },
    ]
    expected_stats = {
        "test:total_energy_import1": expected_stats_inner,
        "test:total_energy_import2": expected_stats_inner,
    }
    assert stats == expected_stats

    # Get change
    stats = statistics_during_period(
        hass,
        start_time=period1,
        statistic_ids={"test:total_energy_import1", "test:total_energy_import2"},
        period="day",
        types={"change"},
    )
    expected_inner = [
        {
            "start": day1_start.timestamp(),
            "end": day1_end.timestamp(),
            "change": 3.0,
        },
        {
            "start": day2_start.timestamp(),
            "end": day2_end.timestamp(),
            "change": 2.0,
        },
        {
            "start": day3_start.timestamp(),
            "end": day3_end.timestamp(),
            "change": 2.0,
        },
    ]
    assert stats == {
        "test:total_energy_import1": expected_inner,
        "test:total_energy_import2": expected_inner,
    }

    # Get data with start during the first period
    stats = statistics_during_period(
        hass,
        start_time=period1 + timedelta(hours=1),
        statistic_ids={"test:total_energy_import1", "test:total_energy_import2"},
        period="day",
    )
    assert stats == expected_stats

    # Get data with end during the third period
    stats = statistics_during_period(
        hass,
        start_time=zero,
        end_time=period6 - timedelta(hours=1),
        statistic_ids={"test:total_energy_import1", "test:total_energy_import2"},
        period="day",
    )
    assert stats == expected_stats

    # Try to get data for entities which do not exist
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids={
            "not",
            "the",
            "same",
            "test:total_energy_import1",
            "test:total_energy_import2",
        },
        period="day",
    )
    assert stats == expected_stats

    # Use 5minute to ensure table switch works
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids=[
            "test:total_energy_import1",
            "with_other",
            "test:total_energy_import2",
        ],
        period="5minute",
    )
    assert stats == {}

    # Ensure future date has not data
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(
        hass, start_time=future, end_time=future, period="day"
    )
    assert stats == {}


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
@pytest.mark.parametrize("timezone", ["America/Regina", "Europe/Vienna", "UTC"])
@pytest.mark.freeze_time("2022-10-01 00:00:00+00:00")
async def test_weekly_statistics_mean(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
    timezone,
) -> None:
    """Test weekly statistics."""
    await hass.config.async_set_time_zone(timezone)
    await async_wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2022-10-05 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2022-10-10 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2022-10-16 23:00:00"))

    external_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "max": 0,
            "mean": 10,
            "min": -100,
        },
        {
            "start": period2,
            "last_reset": None,
            "max": 10,
            "mean": 20,
            "min": -90,
        },
        {
            "start": period3,
            "last_reset": None,
            "max": 20,
            "mean": 30,
            "min": -80,
        },
        {
            "start": period4,
            "last_reset": None,
            "max": 30,
            "mean": 40,
            "min": -70,
        },
    )
    external_metadata = {
        "has_mean": True,
        "has_sum": False,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(hass, external_metadata, external_statistics)
    await async_wait_recording_done(hass)
    # Get all data
    stats = statistics_during_period(
        hass, zero, period="week", statistic_ids={"test:total_energy_import"}
    )
    week1_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 00:00:00"))
    week1_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-10 00:00:00"))
    week2_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-10 00:00:00"))
    week2_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-17 00:00:00"))
    expected_stats = {
        "test:total_energy_import": [
            {
                "start": week1_start.timestamp(),
                "end": week1_end.timestamp(),
                "last_reset": None,
                "max": 10,
                "mean": 15,
                "min": -100,
            },
            {
                "start": week2_start.timestamp(),
                "end": week2_end.timestamp(),
                "last_reset": None,
                "max": 30,
                "mean": 35,
                "min": -80,
            },
        ]
    }
    assert stats == expected_stats

    # Get data starting with start of the first period
    stats = statistics_during_period(
        hass,
        start_time=period1,
        statistic_ids={"test:total_energy_import"},
        period="week",
    )
    assert stats == expected_stats

    # Get data with start during the first period
    stats = statistics_during_period(
        hass,
        start_time=period1 + timedelta(days=1),
        statistic_ids={"test:total_energy_import"},
        period="week",
    )
    assert stats == expected_stats

    # Try to get data for entities which do not exist
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids={"not", "the", "same", "test:total_energy_import"},
        period="week",
    )
    assert stats == expected_stats

    # Use 5minute to ensure table switch works
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids=["test:total_energy_import", "with_other"],
        period="5minute",
    )
    assert stats == {}

    # Ensure future date has not data
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(
        hass, start_time=future, end_time=future, period="week"
    )
    assert stats == {}


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
@pytest.mark.parametrize("timezone", ["America/Regina", "Europe/Vienna", "UTC"])
@pytest.mark.freeze_time("2022-10-01 00:00:00+00:00")
async def test_weekly_statistics_sum(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
    timezone,
) -> None:
    """Test weekly statistics."""
    await hass.config.async_set_time_zone(timezone)
    await async_wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2022-10-09 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2022-10-10 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2022-10-16 23:00:00"))
    period5 = dt_util.as_utc(dt_util.parse_datetime("2022-10-17 00:00:00"))
    period6 = dt_util.as_utc(dt_util.parse_datetime("2022-10-23 23:00:00"))

    external_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 4,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 5,
        },
        {
            "start": period5,
            "last_reset": None,
            "state": 4,
            "sum": 6,
        },
        {
            "start": period6,
            "last_reset": None,
            "state": 5,
            "sum": 7,
        },
    )
    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(hass, external_metadata, external_statistics)
    await async_wait_recording_done(hass)
    stats = statistics_during_period(
        hass, zero, period="week", statistic_ids={"test:total_energy_import"}
    )
    week1_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 00:00:00"))
    week1_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-10 00:00:00"))
    week2_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-10 00:00:00"))
    week2_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-17 00:00:00"))
    week3_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-17 00:00:00"))
    week3_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-24 00:00:00"))
    expected_stats = {
        "test:total_energy_import": [
            {
                "start": week1_start.timestamp(),
                "end": week1_end.timestamp(),
                "last_reset": None,
                "state": 1.0,
                "sum": 3.0,
            },
            {
                "start": week2_start.timestamp(),
                "end": week2_end.timestamp(),
                "last_reset": None,
                "state": 3.0,
                "sum": 5.0,
            },
            {
                "start": week3_start.timestamp(),
                "end": week3_end.timestamp(),
                "last_reset": None,
                "state": 5.0,
                "sum": 7.0,
            },
        ]
    }
    assert stats == expected_stats

    # Get change
    stats = statistics_during_period(
        hass,
        start_time=period1,
        statistic_ids={"test:total_energy_import"},
        period="week",
        types={"change"},
    )
    assert stats == {
        "test:total_energy_import": [
            {
                "start": week1_start.timestamp(),
                "end": week1_end.timestamp(),
                "change": 3.0,
            },
            {
                "start": week2_start.timestamp(),
                "end": week2_end.timestamp(),
                "change": 2.0,
            },
            {
                "start": week3_start.timestamp(),
                "end": week3_end.timestamp(),
                "change": 2.0,
            },
        ]
    }

    # Get data with start during the first period
    stats = statistics_during_period(
        hass,
        start_time=period1 + timedelta(days=1),
        statistic_ids={"test:total_energy_import"},
        period="week",
    )
    assert stats == expected_stats

    # Get data with end during the third period
    stats = statistics_during_period(
        hass,
        start_time=zero,
        end_time=period6 - timedelta(days=1),
        statistic_ids={"test:total_energy_import"},
        period="week",
    )
    assert stats == expected_stats

    # Try to get data for entities which do not exist
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids={"not", "the", "same", "test:total_energy_import"},
        period="week",
    )
    assert stats == expected_stats

    # Use 5minute to ensure table switch works
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids=["test:total_energy_import", "with_other"],
        period="5minute",
    )
    assert stats == {}

    # Ensure future date has not data
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(
        hass, start_time=future, end_time=future, period="week"
    )
    assert stats == {}


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
@pytest.mark.parametrize("timezone", ["America/Regina", "Europe/Vienna", "UTC"])
@pytest.mark.freeze_time("2021-08-01 00:00:00+00:00")
async def test_monthly_statistics_sum(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
    timezone,
) -> None:
    """Test monthly statistics."""
    await hass.config.async_set_time_zone(timezone)
    await async_wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))
    period5 = dt_util.as_utc(dt_util.parse_datetime("2021-11-01 00:00:00"))
    period6 = dt_util.as_utc(dt_util.parse_datetime("2021-11-30 23:00:00"))

    external_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 4,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 5,
        },
        {
            "start": period5,
            "last_reset": None,
            "state": 4,
            "sum": 6,
        },
        {
            "start": period6,
            "last_reset": None,
            "state": 5,
            "sum": 7,
        },
    )
    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(hass, external_metadata, external_statistics)
    await async_wait_recording_done(hass)
    stats = statistics_during_period(
        hass, zero, period="month", statistic_ids={"test:total_energy_import"}
    )
    sep_start = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    sep_end = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    oct_start = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    oct_end = dt_util.as_utc(dt_util.parse_datetime("2021-11-01 00:00:00"))
    nov_start = dt_util.as_utc(dt_util.parse_datetime("2021-11-01 00:00:00"))
    nov_end = dt_util.as_utc(dt_util.parse_datetime("2021-12-01 00:00:00"))
    expected_stats = {
        "test:total_energy_import": [
            {
                "start": sep_start.timestamp(),
                "end": sep_end.timestamp(),
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
            {
                "start": oct_start.timestamp(),
                "end": oct_end.timestamp(),
                "last_reset": None,
                "state": pytest.approx(3.0),
                "sum": pytest.approx(5.0),
            },
            {
                "start": nov_start.timestamp(),
                "end": nov_end.timestamp(),
                "last_reset": None,
                "state": 5.0,
                "sum": 7.0,
            },
        ]
    }
    assert stats == expected_stats

    # Get change
    stats = statistics_during_period(
        hass,
        start_time=period1,
        statistic_ids={"test:total_energy_import"},
        period="month",
        types={"change"},
    )
    assert stats == {
        "test:total_energy_import": [
            {
                "start": sep_start.timestamp(),
                "end": sep_end.timestamp(),
                "change": 3.0,
            },
            {
                "start": oct_start.timestamp(),
                "end": oct_end.timestamp(),
                "change": 2.0,
            },
            {
                "start": nov_start.timestamp(),
                "end": nov_end.timestamp(),
                "change": 2.0,
            },
        ]
    }
    # Get data with start during the first period
    stats = statistics_during_period(
        hass,
        start_time=period1 + timedelta(days=1),
        statistic_ids={"test:total_energy_import"},
        period="month",
    )
    assert stats == expected_stats

    # Get data with end during the third period
    stats = statistics_during_period(
        hass,
        start_time=zero,
        end_time=period6 - timedelta(days=1),
        statistic_ids={"test:total_energy_import"},
        period="month",
    )
    assert stats == expected_stats

    # Try to get data for entities which do not exist
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids={"not", "the", "same", "test:total_energy_import"},
        period="month",
    )
    assert stats == expected_stats

    # Get only sum
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids={"not", "the", "same", "test:total_energy_import"},
        period="month",
        types={"sum"},
    )
    assert stats == {
        "test:total_energy_import": [
            {
                "start": sep_start.timestamp(),
                "end": sep_end.timestamp(),
                "sum": pytest.approx(3.0),
            },
            {
                "start": oct_start.timestamp(),
                "end": oct_end.timestamp(),
                "sum": pytest.approx(5.0),
            },
            {
                "start": nov_start.timestamp(),
                "end": nov_end.timestamp(),
                "sum": pytest.approx(7.0),
            },
        ]
    }

    # Get only sum + convert units
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids={"not", "the", "same", "test:total_energy_import"},
        period="month",
        types={"sum"},
        units={"energy": "Wh"},
    )
    assert stats == {
        "test:total_energy_import": [
            {
                "start": sep_start.timestamp(),
                "end": sep_end.timestamp(),
                "sum": pytest.approx(3000.0),
            },
            {
                "start": oct_start.timestamp(),
                "end": oct_end.timestamp(),
                "sum": pytest.approx(5000.0),
            },
            {
                "start": nov_start.timestamp(),
                "end": nov_end.timestamp(),
                "sum": pytest.approx(7000.0),
            },
        ]
    }

    # Use 5minute to ensure table switch works
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids=["test:total_energy_import", "with_other"],
        period="5minute",
    )
    assert stats == {}

    # Ensure future date has not data
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(
        hass, start_time=future, end_time=future, period="month"
    )
    assert stats == {}


def test_cache_key_for_generate_statistics_during_period_stmt() -> None:
    """Test cache key for _generate_statistics_during_period_stmt."""
    stmt = _generate_statistics_during_period_stmt(
        dt_util.utcnow(), dt_util.utcnow(), [0], StatisticsShortTerm, set()
    )
    cache_key_1 = stmt._generate_cache_key()
    stmt2 = _generate_statistics_during_period_stmt(
        dt_util.utcnow(), dt_util.utcnow(), [0], StatisticsShortTerm, set()
    )
    cache_key_2 = stmt2._generate_cache_key()
    assert cache_key_1 == cache_key_2
    stmt3 = _generate_statistics_during_period_stmt(
        dt_util.utcnow(),
        dt_util.utcnow(),
        [0],
        StatisticsShortTerm,
        {"sum", "mean"},
    )
    cache_key_3 = stmt3._generate_cache_key()
    assert cache_key_1 != cache_key_3


def test_cache_key_for_generate_get_metadata_stmt() -> None:
    """Test cache key for _generate_get_metadata_stmt."""
    stmt_mean = _generate_get_metadata_stmt([0], "mean")
    stmt_mean2 = _generate_get_metadata_stmt([1], "mean")
    stmt_sum = _generate_get_metadata_stmt([0], "sum")
    stmt_none = _generate_get_metadata_stmt()
    assert stmt_mean._generate_cache_key() == stmt_mean2._generate_cache_key()
    assert stmt_mean._generate_cache_key() != stmt_sum._generate_cache_key()
    assert stmt_mean._generate_cache_key() != stmt_none._generate_cache_key()


def test_cache_key_for_generate_max_mean_min_statistic_in_sub_period_stmt() -> None:
    """Test cache key for _generate_max_mean_min_statistic_in_sub_period_stmt."""
    columns = select(StatisticsShortTerm.metadata_id, StatisticsShortTerm.start_ts)
    stmt = _generate_max_mean_min_statistic_in_sub_period_stmt(
        columns,
        dt_util.utcnow(),
        dt_util.utcnow(),
        StatisticsShortTerm,
        [0],
    )
    cache_key_1 = stmt._generate_cache_key()
    stmt2 = _generate_max_mean_min_statistic_in_sub_period_stmt(
        columns,
        dt_util.utcnow(),
        dt_util.utcnow(),
        StatisticsShortTerm,
        [0],
    )
    cache_key_2 = stmt2._generate_cache_key()
    assert cache_key_1 == cache_key_2
    columns2 = select(
        StatisticsShortTerm.metadata_id,
        StatisticsShortTerm.start_ts,
        StatisticsShortTerm.sum,
        StatisticsShortTerm.mean,
    )
    stmt3 = _generate_max_mean_min_statistic_in_sub_period_stmt(
        columns2,
        dt_util.utcnow(),
        dt_util.utcnow(),
        StatisticsShortTerm,
        [0],
    )
    cache_key_3 = stmt3._generate_cache_key()
    assert cache_key_1 != cache_key_3


def test_cache_key_for_generate_statistics_at_time_stmt_group_by() -> None:
    """Test cache key for _generate_statistics_at_time_stmt_group_by."""
    stmt = _generate_statistics_at_time_stmt_group_by(
        StatisticsShortTerm, {0}, 0.0, set()
    )
    cache_key_1 = stmt._generate_cache_key()
    stmt2 = _generate_statistics_at_time_stmt_group_by(
        StatisticsShortTerm, {0}, 0.0, set()
    )
    cache_key_2 = stmt2._generate_cache_key()
    assert cache_key_1 == cache_key_2
    stmt3 = _generate_statistics_at_time_stmt_group_by(
        StatisticsShortTerm, {0}, 0.0, {"sum", "mean"}
    )
    cache_key_3 = stmt3._generate_cache_key()
    assert cache_key_1 != cache_key_3


def test_cache_key_for_generate_statistics_at_time_stmt_dependent_sub_query() -> None:
    """Test cache key for _generate_statistics_at_time_stmt_dependent_sub_query."""
    stmt = _generate_statistics_at_time_stmt_dependent_sub_query(
        StatisticsShortTerm, {0}, 0.0, set()
    )
    cache_key_1 = stmt._generate_cache_key()
    stmt2 = _generate_statistics_at_time_stmt_dependent_sub_query(
        StatisticsShortTerm, {0}, 0.0, set()
    )
    cache_key_2 = stmt2._generate_cache_key()
    assert cache_key_1 == cache_key_2
    stmt3 = _generate_statistics_at_time_stmt_dependent_sub_query(
        StatisticsShortTerm, {0}, 0.0, {"sum", "mean"}
    )
    cache_key_3 = stmt3._generate_cache_key()
    assert cache_key_1 != cache_key_3


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
@pytest.mark.parametrize("timezone", ["America/Regina", "Europe/Vienna", "UTC"])
@pytest.mark.freeze_time("2022-10-01 00:00:00+00:00")
async def test_change(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
    timezone,
) -> None:
    """Test deriving change from sum statistic."""
    await hass.config.async_set_time_zone(timezone)
    await async_wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 01:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 02:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 03:00:00"))

    external_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 5,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 8,
        },
    )
    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "recorder",
        "statistic_id": "sensor.total_energy_import",
        "unit_of_measurement": "kWh",
    }

    async_import_statistics(hass, external_metadata, external_statistics)
    await async_wait_recording_done(hass)
    # Get change from far in the past
    stats = statistics_during_period(
        hass,
        zero,
        period="hour",
        statistic_ids={"sensor.total_energy_import"},
        types={"change"},
    )
    hour1_start = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 00:00:00"))
    hour1_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 01:00:00"))
    hour2_start = hour1_end
    hour2_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 02:00:00"))
    hour3_start = hour2_end
    hour3_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 03:00:00"))
    hour4_start = hour3_end
    hour4_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 04:00:00"))
    expected_stats = {
        "sensor.total_energy_import": [
            {
                "start": hour1_start.timestamp(),
                "end": hour1_end.timestamp(),
                "change": 2.0,
            },
            {
                "start": hour2_start.timestamp(),
                "end": hour2_end.timestamp(),
                "change": 1.0,
            },
            {
                "start": hour3_start.timestamp(),
                "end": hour3_end.timestamp(),
                "change": 2.0,
            },
            {
                "start": hour4_start.timestamp(),
                "end": hour4_end.timestamp(),
                "change": 3.0,
            },
        ]
    }
    assert stats == expected_stats

    # Get change + sum from far in the past
    stats = statistics_during_period(
        hass,
        zero,
        period="hour",
        statistic_ids={"sensor.total_energy_import"},
        types={"change", "sum"},
    )
    hour1_start = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 00:00:00"))
    hour1_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 01:00:00"))
    hour2_start = hour1_end
    hour2_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 02:00:00"))
    hour3_start = hour2_end
    hour3_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 03:00:00"))
    hour4_start = hour3_end
    hour4_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 04:00:00"))
    expected_stats_change_sum = {
        "sensor.total_energy_import": [
            {
                "start": hour1_start.timestamp(),
                "end": hour1_end.timestamp(),
                "change": 2.0,
                "sum": 2.0,
            },
            {
                "start": hour2_start.timestamp(),
                "end": hour2_end.timestamp(),
                "change": 1.0,
                "sum": 3.0,
            },
            {
                "start": hour3_start.timestamp(),
                "end": hour3_end.timestamp(),
                "change": 2.0,
                "sum": 5.0,
            },
            {
                "start": hour4_start.timestamp(),
                "end": hour4_end.timestamp(),
                "change": 3.0,
                "sum": 8.0,
            },
        ]
    }
    assert stats == expected_stats_change_sum

    # Get change from far in the past with unit conversion
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"sensor.total_energy_import"},
        period="hour",
        types={"change"},
        units={"energy": "Wh"},
    )
    expected_stats_wh = {
        "sensor.total_energy_import": [
            {
                "start": hour1_start.timestamp(),
                "end": hour1_end.timestamp(),
                "change": 2.0 * 1000,
            },
            {
                "start": hour2_start.timestamp(),
                "end": hour2_end.timestamp(),
                "change": 1.0 * 1000,
            },
            {
                "start": hour3_start.timestamp(),
                "end": hour3_end.timestamp(),
                "change": 2.0 * 1000,
            },
            {
                "start": hour4_start.timestamp(),
                "end": hour4_end.timestamp(),
                "change": 3.0 * 1000,
            },
        ]
    }
    assert stats == expected_stats_wh

    # Get change from far in the past with implicit unit conversion
    hass.states.async_set(
        "sensor.total_energy_import", "unknown", {"unit_of_measurement": "MWh"}
    )
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"sensor.total_energy_import"},
        period="hour",
        types={"change"},
    )
    expected_stats_mwh = {
        "sensor.total_energy_import": [
            {
                "start": hour1_start.timestamp(),
                "end": hour1_end.timestamp(),
                "change": 2.0 / 1000,
            },
            {
                "start": hour2_start.timestamp(),
                "end": hour2_end.timestamp(),
                "change": 1.0 / 1000,
            },
            {
                "start": hour3_start.timestamp(),
                "end": hour3_end.timestamp(),
                "change": 2.0 / 1000,
            },
            {
                "start": hour4_start.timestamp(),
                "end": hour4_end.timestamp(),
                "change": 3.0 / 1000,
            },
        ]
    }
    assert stats == expected_stats_mwh
    hass.states.async_remove("sensor.total_energy_import")

    # Get change from the first recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"sensor.total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == expected_stats

    # Get change from the first recorded hour with unit conversion
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"sensor.total_energy_import"},
        period="hour",
        types={"change"},
        units={"energy": "Wh"},
    )
    assert stats == expected_stats_wh

    # Get change from the first recorded hour with implicit unit conversion
    hass.states.async_set(
        "sensor.total_energy_import", "unknown", {"unit_of_measurement": "MWh"}
    )
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"sensor.total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == expected_stats_mwh
    hass.states.async_remove("sensor.total_energy_import")

    # Get change from the second recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour2_start,
        statistic_ids={"sensor.total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == {
        "sensor.total_energy_import": expected_stats["sensor.total_energy_import"][1:4]
    }

    # Get change from the second recorded hour with unit conversion
    stats = statistics_during_period(
        hass,
        start_time=hour2_start,
        statistic_ids={"sensor.total_energy_import"},
        period="hour",
        types={"change"},
        units={"energy": "Wh"},
    )
    assert stats == {
        "sensor.total_energy_import": expected_stats_wh["sensor.total_energy_import"][
            1:4
        ]
    }

    # Get change from the second recorded hour with implicit unit conversion
    hass.states.async_set(
        "sensor.total_energy_import", "unknown", {"unit_of_measurement": "MWh"}
    )
    stats = statistics_during_period(
        hass,
        start_time=hour2_start,
        statistic_ids={"sensor.total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == {
        "sensor.total_energy_import": expected_stats_mwh["sensor.total_energy_import"][
            1:4
        ]
    }
    hass.states.async_remove("sensor.total_energy_import")

    # Get change from the second until the third recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour2_start,
        end_time=hour4_start,
        statistic_ids={"sensor.total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == {
        "sensor.total_energy_import": expected_stats["sensor.total_energy_import"][1:3]
    }

    # Get change from the fourth recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour4_start,
        statistic_ids={"sensor.total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == {
        "sensor.total_energy_import": expected_stats["sensor.total_energy_import"][3:4]
    }

    # Test change with a far future start date
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(
        hass,
        start_time=future,
        statistic_ids={"sensor.total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == {}


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
@pytest.mark.parametrize("timezone", ["America/Regina", "Europe/Vienna", "UTC"])
@pytest.mark.freeze_time("2022-10-01 00:00:00+00:00")
async def test_change_multiple(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
    timezone,
) -> None:
    """Test deriving change from sum statistic."""
    await hass.config.async_set_time_zone(timezone)
    await async_wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 01:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 02:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 03:00:00"))

    external_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 5,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 8,
        },
    )
    external_metadata1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "recorder",
        "statistic_id": "sensor.total_energy_import1",
        "unit_of_measurement": "kWh",
    }
    external_metadata2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "recorder",
        "statistic_id": "sensor.total_energy_import2",
        "unit_of_measurement": "kWh",
    }
    async_import_statistics(hass, external_metadata1, external_statistics)
    async_import_statistics(hass, external_metadata2, external_statistics)
    await async_wait_recording_done(hass)
    # Get change from far in the past
    stats = statistics_during_period(
        hass,
        zero,
        period="hour",
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        types={"change"},
    )
    hour1_start = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 00:00:00"))
    hour1_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 01:00:00"))
    hour2_start = hour1_end
    hour2_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 02:00:00"))
    hour3_start = hour2_end
    hour3_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 03:00:00"))
    hour4_start = hour3_end
    hour4_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 04:00:00"))
    expected_inner = [
        {
            "start": hour1_start.timestamp(),
            "end": hour1_end.timestamp(),
            "change": 2.0,
        },
        {
            "start": hour2_start.timestamp(),
            "end": hour2_end.timestamp(),
            "change": 1.0,
        },
        {
            "start": hour3_start.timestamp(),
            "end": hour3_end.timestamp(),
            "change": 2.0,
        },
        {
            "start": hour4_start.timestamp(),
            "end": hour4_end.timestamp(),
            "change": 3.0,
        },
    ]
    expected_stats = {
        "sensor.total_energy_import1": expected_inner,
        "sensor.total_energy_import2": expected_inner,
    }
    assert stats == expected_stats

    # Get change + sum from far in the past
    stats = statistics_during_period(
        hass,
        zero,
        period="hour",
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        types={"change", "sum"},
    )
    hour1_start = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 00:00:00"))
    hour1_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 01:00:00"))
    hour2_start = hour1_end
    hour2_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 02:00:00"))
    hour3_start = hour2_end
    hour3_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 03:00:00"))
    hour4_start = hour3_end
    hour4_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 04:00:00"))
    expected_inner = [
        {
            "start": hour1_start.timestamp(),
            "end": hour1_end.timestamp(),
            "change": 2.0,
            "sum": 2.0,
        },
        {
            "start": hour2_start.timestamp(),
            "end": hour2_end.timestamp(),
            "change": 1.0,
            "sum": 3.0,
        },
        {
            "start": hour3_start.timestamp(),
            "end": hour3_end.timestamp(),
            "change": 2.0,
            "sum": 5.0,
        },
        {
            "start": hour4_start.timestamp(),
            "end": hour4_end.timestamp(),
            "change": 3.0,
            "sum": 8.0,
        },
    ]
    expected_stats_change_sum = {
        "sensor.total_energy_import1": expected_inner,
        "sensor.total_energy_import2": expected_inner,
    }
    assert stats == expected_stats_change_sum

    # Get change from far in the past with unit conversion
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        period="hour",
        types={"change"},
        units={"energy": "Wh"},
    )
    expected_inner = [
        {
            "start": hour1_start.timestamp(),
            "end": hour1_end.timestamp(),
            "change": 2.0 * 1000,
        },
        {
            "start": hour2_start.timestamp(),
            "end": hour2_end.timestamp(),
            "change": 1.0 * 1000,
        },
        {
            "start": hour3_start.timestamp(),
            "end": hour3_end.timestamp(),
            "change": 2.0 * 1000,
        },
        {
            "start": hour4_start.timestamp(),
            "end": hour4_end.timestamp(),
            "change": 3.0 * 1000,
        },
    ]
    expected_stats_wh = {
        "sensor.total_energy_import1": expected_inner,
        "sensor.total_energy_import2": expected_inner,
    }
    assert stats == expected_stats_wh

    # Get change from far in the past with implicit unit conversion
    hass.states.async_set(
        "sensor.total_energy_import1", "unknown", {"unit_of_measurement": "MWh"}
    )
    hass.states.async_set(
        "sensor.total_energy_import2", "unknown", {"unit_of_measurement": "MWh"}
    )
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        period="hour",
        types={"change"},
    )
    expected_inner = [
        {
            "start": hour1_start.timestamp(),
            "end": hour1_end.timestamp(),
            "change": 2.0 / 1000,
        },
        {
            "start": hour2_start.timestamp(),
            "end": hour2_end.timestamp(),
            "change": 1.0 / 1000,
        },
        {
            "start": hour3_start.timestamp(),
            "end": hour3_end.timestamp(),
            "change": 2.0 / 1000,
        },
        {
            "start": hour4_start.timestamp(),
            "end": hour4_end.timestamp(),
            "change": 3.0 / 1000,
        },
    ]
    expected_stats_mwh = {
        "sensor.total_energy_import1": expected_inner,
        "sensor.total_energy_import2": expected_inner,
    }
    assert stats == expected_stats_mwh
    hass.states.async_remove("sensor.total_energy_import1")
    hass.states.async_remove("sensor.total_energy_import2")

    # Get change from the first recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        period="hour",
        types={"change"},
    )
    assert stats == expected_stats

    # Get change from the first recorded hour with unit conversion
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        period="hour",
        types={"change"},
        units={"energy": "Wh"},
    )
    assert stats == expected_stats_wh

    # Get change from the first recorded hour with implicit unit conversion
    hass.states.async_set(
        "sensor.total_energy_import1", "unknown", {"unit_of_measurement": "MWh"}
    )
    hass.states.async_set(
        "sensor.total_energy_import2", "unknown", {"unit_of_measurement": "MWh"}
    )
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        period="hour",
        types={"change"},
    )
    assert stats == expected_stats_mwh
    hass.states.async_remove("sensor.total_energy_import1")
    hass.states.async_remove("sensor.total_energy_import2")

    # Get change from the second recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour2_start,
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        period="hour",
        types={"change"},
    )
    assert stats == {
        "sensor.total_energy_import1": expected_stats["sensor.total_energy_import1"][
            1:4
        ],
        "sensor.total_energy_import2": expected_stats["sensor.total_energy_import2"][
            1:4
        ],
    }

    # Get change from the second recorded hour with unit conversion
    stats = statistics_during_period(
        hass,
        start_time=hour2_start,
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        period="hour",
        types={"change"},
        units={"energy": "Wh"},
    )
    assert stats == {
        "sensor.total_energy_import1": expected_stats_wh["sensor.total_energy_import1"][
            1:4
        ],
        "sensor.total_energy_import2": expected_stats_wh["sensor.total_energy_import2"][
            1:4
        ],
    }

    # Get change from the second recorded hour with implicit unit conversion
    hass.states.async_set(
        "sensor.total_energy_import1", "unknown", {"unit_of_measurement": "MWh"}
    )
    hass.states.async_set(
        "sensor.total_energy_import2", "unknown", {"unit_of_measurement": "MWh"}
    )
    stats = statistics_during_period(
        hass,
        start_time=hour2_start,
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        period="hour",
        types={"change"},
    )
    assert stats == {
        "sensor.total_energy_import1": expected_stats_mwh[
            "sensor.total_energy_import1"
        ][1:4],
        "sensor.total_energy_import2": expected_stats_mwh[
            "sensor.total_energy_import2"
        ][1:4],
    }
    hass.states.async_remove("sensor.total_energy_import1")
    hass.states.async_remove("sensor.total_energy_import2")

    # Get change from the second until the third recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour2_start,
        end_time=hour4_start,
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        period="hour",
        types={"change"},
    )
    assert stats == {
        "sensor.total_energy_import1": expected_stats["sensor.total_energy_import1"][
            1:3
        ],
        "sensor.total_energy_import2": expected_stats["sensor.total_energy_import2"][
            1:3
        ],
    }

    # Get change from the fourth recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour4_start,
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        period="hour",
        types={"change"},
    )
    assert stats == {
        "sensor.total_energy_import1": expected_stats["sensor.total_energy_import1"][
            3:4
        ],
        "sensor.total_energy_import2": expected_stats["sensor.total_energy_import2"][
            3:4
        ],
    }

    # Test change with a far future start date
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(
        hass,
        start_time=future,
        statistic_ids={"sensor.total_energy_import1", "sensor.total_energy_import2"},
        period="hour",
        types={"change"},
    )
    assert stats == {}


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
@pytest.mark.parametrize("timezone", ["America/Regina", "Europe/Vienna", "UTC"])
@pytest.mark.freeze_time("2022-10-01 00:00:00+00:00")
async def test_change_with_none(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
    timezone,
) -> None:
    """Test deriving change from sum statistic.

    This tests the behavior when some record has None sum. The calculated change
    is not expected to be correct, but we should not raise on this error.
    """
    await hass.config.async_set_time_zone(timezone)
    await async_wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 01:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 02:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 03:00:00"))

    external_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": None,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 8,
        },
    )
    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(hass, external_metadata, external_statistics)
    await async_wait_recording_done(hass)
    # Get change from far in the past
    stats = statistics_during_period(
        hass,
        zero,
        period="hour",
        statistic_ids={"test:total_energy_import"},
        types={"change"},
    )
    hour1_start = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 00:00:00"))
    hour1_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 01:00:00"))
    hour2_start = hour1_end
    hour2_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 02:00:00"))
    hour3_start = hour2_end
    hour3_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 03:00:00"))
    hour4_start = hour3_end
    hour4_end = dt_util.as_utc(dt_util.parse_datetime("2023-05-08 04:00:00"))
    expected_stats = {
        "test:total_energy_import": [
            {
                "start": hour1_start.timestamp(),
                "end": hour1_end.timestamp(),
                "change": 2.0,
            },
            {
                "start": hour2_start.timestamp(),
                "end": hour2_end.timestamp(),
                "change": 1.0,
            },
            {
                "start": hour3_start.timestamp(),
                "end": hour3_end.timestamp(),
                "change": None,
            },
            {
                "start": hour4_start.timestamp(),
                "end": hour4_end.timestamp(),
                "change": 5.0,
            },
        ]
    }
    assert stats == expected_stats

    # Get change from far in the past with unit conversion
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"test:total_energy_import"},
        period="hour",
        types={"change"},
        units={"energy": "Wh"},
    )
    expected_stats_wh = {
        "test:total_energy_import": [
            {
                "start": hour1_start.timestamp(),
                "end": hour1_end.timestamp(),
                "change": 2.0 * 1000,
            },
            {
                "start": hour2_start.timestamp(),
                "end": hour2_end.timestamp(),
                "change": 1.0 * 1000,
            },
            {
                "start": hour3_start.timestamp(),
                "end": hour3_end.timestamp(),
                "change": None,
            },
            {
                "start": hour4_start.timestamp(),
                "end": hour4_end.timestamp(),
                "change": 5.0 * 1000,
            },
        ]
    }
    assert stats == expected_stats_wh

    # Get change from the first recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"test:total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == expected_stats

    # Get change from the first recorded hour with unit conversion
    stats = statistics_during_period(
        hass,
        start_time=hour1_start,
        statistic_ids={"test:total_energy_import"},
        period="hour",
        types={"change"},
        units={"energy": "Wh"},
    )
    assert stats == expected_stats_wh

    # Get change from the second recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour2_start,
        statistic_ids={"test:total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == {
        "test:total_energy_import": expected_stats["test:total_energy_import"][1:4]
    }

    # Get change from the second recorded hour with unit conversion
    stats = statistics_during_period(
        hass,
        start_time=hour2_start,
        statistic_ids={"test:total_energy_import"},
        period="hour",
        types={"change"},
        units={"energy": "Wh"},
    )
    assert stats == {
        "test:total_energy_import": expected_stats_wh["test:total_energy_import"][1:4]
    }

    # Get change from the second until the third recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour2_start,
        end_time=hour4_start,
        statistic_ids={"test:total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == {
        "test:total_energy_import": expected_stats["test:total_energy_import"][1:3]
    }

    # Get change from the fourth recorded hour
    stats = statistics_during_period(
        hass,
        start_time=hour4_start,
        statistic_ids={"test:total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == {
        "test:total_energy_import": [
            {
                "start": hour4_start.timestamp(),
                "end": hour4_end.timestamp(),
                "change": 8.0,  # Assumed to be 8 because the previous hour has no data
            },
        ]
    }

    # Test change with a far future start date
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(
        hass,
        start_time=future,
        statistic_ids={"test:total_energy_import"},
        period="hour",
        types={"change"},
    )
    assert stats == {}


async def test_recorder_platform_with_statistics(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test recorder platform."""
    instance = recorder.get_instance(hass)
    recorder_data = hass.data["recorder"]
    assert not recorder_data.recorder_platforms

    def _mock_compile_statistics(*args: Any) -> PlatformCompiledStatistics:
        return PlatformCompiledStatistics([], {})

    def _mock_list_statistic_ids(*args: Any, **kwargs: Any) -> dict:
        return {}

    def _mock_validate_statistics(*args: Any) -> dict:
        return {}

    recorder_platform = Mock(
        compile_statistics=Mock(wraps=_mock_compile_statistics),
        list_statistic_ids=Mock(wraps=_mock_list_statistic_ids),
        update_statistics_issues=Mock(),
        validate_statistics=Mock(wraps=_mock_validate_statistics),
    )

    await _setup_mock_domain(hass, recorder_platform)

    # Wait for the sensor recorder platform to be added
    await async_recorder_block_till_done(hass)
    assert recorder_data.recorder_platforms == {"some_domain": recorder_platform}

    recorder_platform.compile_statistics.assert_not_called()
    recorder_platform.list_statistic_ids.assert_not_called()
    recorder_platform.update_statistics_issues.assert_not_called()
    recorder_platform.validate_statistics.assert_not_called()

    # Test compile statistics + update statistics issues
    # Issues are updated hourly when minutes = 50, trigger one hour later to make
    # sure statistics is not suppressed by an existing row in StatisticsRuns
    zero = get_start_time(dt_util.utcnow()).replace(minute=50) + timedelta(hours=1)
    do_adhoc_statistics(hass, start=zero)
    await async_wait_recording_done(hass)

    recorder_platform.compile_statistics.assert_called_once_with(
        hass, ANY, zero, zero + timedelta(minutes=5)
    )
    recorder_platform.update_statistics_issues.assert_called_once_with(hass, ANY)
    recorder_platform.list_statistic_ids.assert_not_called()
    recorder_platform.validate_statistics.assert_not_called()

    # Test list statistic IDs
    await async_list_statistic_ids(hass)
    recorder_platform.compile_statistics.assert_called_once()
    recorder_platform.list_statistic_ids.assert_called_once_with(
        hass, statistic_ids=None, statistic_type=None
    )
    recorder_platform.update_statistics_issues.assert_called_once()
    recorder_platform.validate_statistics.assert_not_called()

    # Test validate statistics
    await instance.async_add_executor_job(
        validate_statistics,
        hass,
    )
    recorder_platform.compile_statistics.assert_called_once()
    recorder_platform.list_statistic_ids.assert_called_once()
    recorder_platform.update_statistics_issues.assert_called_once()
    recorder_platform.validate_statistics.assert_called_once_with(hass)


async def test_recorder_platform_without_statistics(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test recorder platform."""
    recorder_data = hass.data["recorder"]
    assert recorder_data.recorder_platforms == {}

    await _setup_mock_domain(hass)

    # Wait for the sensor recorder platform to be added
    await async_recorder_block_till_done(hass)
    assert recorder_data.recorder_platforms == {}


@pytest.mark.parametrize(
    "supported_methods",
    [
        ("compile_statistics",),
        ("list_statistic_ids",),
        ("update_statistics_issues",),
        ("validate_statistics",),
    ],
)
async def test_recorder_platform_with_partial_statistics_support(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
    supported_methods: tuple[str, ...],
) -> None:
    """Test recorder platform."""
    instance = recorder.get_instance(hass)
    recorder_data = hass.data["recorder"]
    assert not recorder_data.recorder_platforms

    def _mock_compile_statistics(*args: Any) -> PlatformCompiledStatistics:
        return PlatformCompiledStatistics([], {})

    def _mock_list_statistic_ids(*args: Any, **kwargs: Any) -> dict:
        return {}

    def _mock_validate_statistics(*args: Any) -> dict:
        return {}

    mock_impl = {
        "compile_statistics": _mock_compile_statistics,
        "list_statistic_ids": _mock_list_statistic_ids,
        "update_statistics_issues": None,
        "validate_statistics": _mock_validate_statistics,
    }

    kwargs = {meth: Mock(wraps=mock_impl[meth]) for meth in supported_methods}

    recorder_platform = Mock(
        spec=supported_methods,
        **kwargs,
    )

    await _setup_mock_domain(hass, recorder_platform)

    # Wait for the sensor recorder platform to be added
    await async_recorder_block_till_done(hass)
    assert recorder_data.recorder_platforms == {"some_domain": recorder_platform}

    for meth in supported_methods:
        getattr(recorder_platform, meth).assert_not_called()

    # Test compile statistics + update statistics issues
    # Issues are updated hourly when minutes = 50, trigger one hour later to make
    # sure statistics is not suppressed by an existing row in StatisticsRuns
    zero = get_start_time(dt_util.utcnow()).replace(minute=50) + timedelta(hours=1)
    do_adhoc_statistics(hass, start=zero)
    await async_wait_recording_done(hass)

    # Test list statistic IDs
    await async_list_statistic_ids(hass)

    # Test validate statistics
    await instance.async_add_executor_job(
        validate_statistics,
        hass,
    )

    for meth in supported_methods:
        getattr(recorder_platform, meth).assert_called_once()
