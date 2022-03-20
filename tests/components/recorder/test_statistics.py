"""The tests for sensor recorder platform."""
# pylint: disable=protected-access,invalid-name
from datetime import timedelta
import importlib
import json
import sys
from unittest.mock import patch, sentinel

import pytest
from pytest import approx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import SQLITE_URL_PREFIX, history, statistics
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.models import (
    StatisticsShortTerm,
    process_timestamp_to_utc_isoformat,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    delete_duplicates,
    get_last_short_term_statistics,
    get_last_statistics,
    get_metadata,
    list_statistic_ids,
    statistics_during_period,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant, mock_registry
from tests.components.recorder.common import wait_recording_done

ORIG_TZ = dt_util.DEFAULT_TIME_ZONE


def test_compile_hourly_statistics(hass_recorder):
    """Test compiling hourly statistics."""
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    for kwargs in ({}, {"statistic_ids": ["sensor.test1"]}):
        stats = statistics_during_period(hass, zero, period="5minute", **kwargs)
        assert stats == {}
    stats = get_last_short_term_statistics(hass, 0, "sensor.test1", True)
    assert stats == {}

    recorder.do_adhoc_statistics(start=zero)
    recorder.do_adhoc_statistics(start=four)
    wait_recording_done(hass)
    expected_1 = {
        "statistic_id": "sensor.test1",
        "start": process_timestamp_to_utc_isoformat(zero),
        "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
        "mean": approx(14.915254237288135),
        "min": approx(10.0),
        "max": approx(20.0),
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_2 = {
        "statistic_id": "sensor.test1",
        "start": process_timestamp_to_utc_isoformat(four),
        "end": process_timestamp_to_utc_isoformat(four + timedelta(minutes=5)),
        "mean": approx(20.0),
        "min": approx(20.0),
        "max": approx(20.0),
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_stats1 = [
        {**expected_1, "statistic_id": "sensor.test1"},
        {**expected_2, "statistic_id": "sensor.test1"},
    ]
    expected_stats2 = [
        {**expected_1, "statistic_id": "sensor.test2"},
        {**expected_2, "statistic_id": "sensor.test2"},
    ]

    # Test statistics_during_period
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {"sensor.test1": expected_stats1, "sensor.test2": expected_stats2}

    stats = statistics_during_period(
        hass, zero, statistic_ids=["sensor.test2"], period="5minute"
    )
    assert stats == {"sensor.test2": expected_stats2}

    stats = statistics_during_period(
        hass, zero, statistic_ids=["sensor.test3"], period="5minute"
    )
    assert stats == {}

    # Test get_last_short_term_statistics
    stats = get_last_short_term_statistics(hass, 0, "sensor.test1", True)
    assert stats == {}

    stats = get_last_short_term_statistics(hass, 1, "sensor.test1", True)
    assert stats == {"sensor.test1": [{**expected_2, "statistic_id": "sensor.test1"}]}

    stats = get_last_short_term_statistics(hass, 2, "sensor.test1", True)
    assert stats == {"sensor.test1": expected_stats1[::-1]}

    stats = get_last_short_term_statistics(hass, 3, "sensor.test1", True)
    assert stats == {"sensor.test1": expected_stats1[::-1]}

    stats = get_last_short_term_statistics(hass, 1, "sensor.test3", True)
    assert stats == {}


@pytest.fixture
def mock_sensor_statistics():
    """Generate some fake statistics."""

    def sensor_stats(entity_id, start):
        """Generate fake statistics."""
        return {
            "meta": {
                "statistic_id": entity_id,
                "unit_of_measurement": "dogs",
                "has_mean": True,
                "has_sum": False,
            },
            "stat": {"start": start},
        }

    def get_fake_stats(_hass, start, _end):
        return [
            sensor_stats("sensor.test1", start),
            sensor_stats("sensor.test2", start),
            sensor_stats("sensor.test3", start),
        ]

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

    def from_stats(metadata_id, stats):
        nonlocal counter
        if counter == 0 and metadata_id == 2:
            counter += 1
            return None
        return real_from_stats(metadata_id, stats)

    with patch(
        "homeassistant.components.recorder.statistics.StatisticsShortTerm.from_stats",
        side_effect=from_stats,
        autospec=True,
    ):
        yield


def test_compile_periodic_statistics_exception(
    hass_recorder, mock_sensor_statistics, mock_from_stats
):
    """Test exception handling when compiling periodic statistics."""

    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})

    now = dt_util.utcnow()
    recorder.do_adhoc_statistics(start=now)
    recorder.do_adhoc_statistics(start=now + timedelta(minutes=5))
    wait_recording_done(hass)
    expected_1 = {
        "statistic_id": "sensor.test1",
        "start": process_timestamp_to_utc_isoformat(now),
        "end": process_timestamp_to_utc_isoformat(now + timedelta(minutes=5)),
        "mean": None,
        "min": None,
        "max": None,
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_2 = {
        "statistic_id": "sensor.test1",
        "start": process_timestamp_to_utc_isoformat(now + timedelta(minutes=5)),
        "end": process_timestamp_to_utc_isoformat(now + timedelta(minutes=10)),
        "mean": None,
        "min": None,
        "max": None,
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_stats1 = [
        {**expected_1, "statistic_id": "sensor.test1"},
        {**expected_2, "statistic_id": "sensor.test1"},
    ]
    expected_stats2 = [
        {**expected_2, "statistic_id": "sensor.test2"},
    ]
    expected_stats3 = [
        {**expected_1, "statistic_id": "sensor.test3"},
        {**expected_2, "statistic_id": "sensor.test3"},
    ]

    stats = statistics_during_period(hass, now, period="5minute")
    assert stats == {
        "sensor.test1": expected_stats1,
        "sensor.test2": expected_stats2,
        "sensor.test3": expected_stats3,
    }


def test_rename_entity(hass_recorder):
    """Test statistics is migrated when entity_id is changed."""
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})

    entity_reg = mock_registry(hass)

    @callback
    def add_entry():
        reg_entry = entity_reg.async_get_or_create(
            "sensor",
            "test",
            "unique_0000",
            suggested_object_id="test1",
        )
        assert reg_entry.entity_id == "sensor.test1"

    hass.add_job(add_entry)
    hass.block_till_done()

    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    for kwargs in ({}, {"statistic_ids": ["sensor.test1"]}):
        stats = statistics_during_period(hass, zero, period="5minute", **kwargs)
        assert stats == {}
    stats = get_last_short_term_statistics(hass, 0, "sensor.test1", True)
    assert stats == {}

    recorder.do_adhoc_statistics(start=zero)
    wait_recording_done(hass)
    expected_1 = {
        "statistic_id": "sensor.test1",
        "start": process_timestamp_to_utc_isoformat(zero),
        "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
        "mean": approx(14.915254237288135),
        "min": approx(10.0),
        "max": approx(20.0),
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_stats1 = [
        {**expected_1, "statistic_id": "sensor.test1"},
    ]
    expected_stats2 = [
        {**expected_1, "statistic_id": "sensor.test2"},
    ]
    expected_stats99 = [
        {**expected_1, "statistic_id": "sensor.test99"},
    ]

    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {"sensor.test1": expected_stats1, "sensor.test2": expected_stats2}

    @callback
    def rename_entry():
        entity_reg.async_update_entity("sensor.test1", new_entity_id="sensor.test99")

    hass.add_job(rename_entry)
    hass.block_till_done()

    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {"sensor.test99": expected_stats99, "sensor.test2": expected_stats2}


def test_statistics_duplicated(hass_recorder, caplog):
    """Test statistics with same start time is not compiled."""
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    with patch(
        "homeassistant.components.sensor.recorder.compile_statistics"
    ) as compile_statistics:
        recorder.do_adhoc_statistics(start=zero)
        wait_recording_done(hass)
        assert compile_statistics.called
        compile_statistics.reset_mock()
        assert "Compiling statistics for" in caplog.text
        assert "Statistics already compiled" not in caplog.text
        caplog.clear()

        recorder.do_adhoc_statistics(start=zero)
        wait_recording_done(hass)
        assert not compile_statistics.called
        compile_statistics.reset_mock()
        assert "Compiling statistics for" not in caplog.text
        assert "Statistics already compiled" in caplog.text
        caplog.clear()


def test_external_statistics(hass_recorder, caplog):
    """Test inserting external statistics."""
    hass = hass_recorder()
    wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    period2 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    external_statistics1 = {
        "start": period1,
        "last_reset": None,
        "state": 0,
        "sum": 2,
    }
    external_statistics2 = {
        "start": period2,
        "last_reset": None,
        "state": 1,
        "sum": 3,
    }

    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(
        hass, external_metadata, (external_statistics1, external_statistics2)
    )
    wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        "test:total_energy_import": [
            {
                "statistic_id": "test:total_energy_import",
                "start": period1.isoformat(),
                "end": (period1 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(0.0),
                "sum": approx(2.0),
            },
            {
                "statistic_id": "test:total_energy_import",
                "start": period2.isoformat(),
                "end": (period2 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(1.0),
                "sum": approx(3.0),
            },
        ]
    }
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "test:total_energy_import",
            "name": "Total imported energy",
            "source": "test",
            "unit_of_measurement": "kWh",
        }
    ]
    metadata = get_metadata(hass, statistic_ids=("test:total_energy_import",))
    assert metadata == {
        "test:total_energy_import": (
            1,
            {
                "has_mean": False,
                "has_sum": True,
                "name": "Total imported energy",
                "source": "test",
                "statistic_id": "test:total_energy_import",
                "unit_of_measurement": "kWh",
            },
        )
    }
    last_stats = get_last_statistics(hass, 1, "test:total_energy_import", True)
    assert last_stats == {
        "test:total_energy_import": [
            {
                "statistic_id": "test:total_energy_import",
                "start": period2.isoformat(),
                "end": (period2 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(1.0),
                "sum": approx(3.0),
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
    async_add_external_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        "test:total_energy_import": [
            {
                "statistic_id": "test:total_energy_import",
                "start": period1.isoformat(),
                "end": (period1 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(5.0),
                "sum": approx(6.0),
            },
            {
                "statistic_id": "test:total_energy_import",
                "start": period2.isoformat(),
                "end": (period2 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(1.0),
                "sum": approx(3.0),
            },
        ]
    }

    # Update the previously inserted statistics
    external_statistics = {
        "start": period1,
        "max": 1,
        "mean": 2,
        "min": 3,
        "last_reset": None,
        "state": 4,
        "sum": 5,
    }
    async_add_external_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        "test:total_energy_import": [
            {
                "statistic_id": "test:total_energy_import",
                "start": period1.isoformat(),
                "end": (period1 + timedelta(hours=1)).isoformat(),
                "max": approx(1.0),
                "mean": approx(2.0),
                "min": approx(3.0),
                "last_reset": None,
                "state": approx(4.0),
                "sum": approx(5.0),
            },
            {
                "statistic_id": "test:total_energy_import",
                "start": period2.isoformat(),
                "end": (period2 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(1.0),
                "sum": approx(3.0),
            },
        ]
    }


def test_external_statistics_errors(hass_recorder, caplog):
    """Test validation of external statistics."""
    hass = hass_recorder()
    wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    _external_statistics = {
        "start": period1,
        "last_reset": None,
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
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("sensor.total_energy_import",)) == {}

    # Attempt to insert statistics for the wrong domain
    external_metadata = {**_external_metadata, "source": "other"}
    external_statistics = {**_external_statistics}
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("test:total_energy_import",)) == {}

    # Attempt to insert statistics for an naive starting time
    external_metadata = {**_external_metadata}
    external_statistics = {
        **_external_statistics,
        "start": period1.replace(tzinfo=None),
    }
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("test:total_energy_import",)) == {}

    # Attempt to insert statistics for an invalid starting time
    external_metadata = {**_external_metadata}
    external_statistics = {**_external_statistics, "start": period1.replace(minute=1)}
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("test:total_energy_import",)) == {}


@pytest.mark.parametrize("timezone", ["America/Regina", "Europe/Vienna", "UTC"])
@pytest.mark.freeze_time("2021-08-01 00:00:00+00:00")
def test_monthly_statistics(hass_recorder, caplog, timezone):
    """Test inserting external statistics."""
    dt_util.set_default_time_zone(dt_util.get_time_zone(timezone))

    hass = hass_recorder()
    wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))

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
    wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="month")
    sep_start = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    sep_end = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    oct_start = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    oct_end = dt_util.as_utc(dt_util.parse_datetime("2021-11-01 00:00:00"))
    assert stats == {
        "test:total_energy_import": [
            {
                "statistic_id": "test:total_energy_import",
                "start": sep_start.isoformat(),
                "end": sep_end.isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(1.0),
                "sum": approx(3.0),
            },
            {
                "statistic_id": "test:total_energy_import",
                "start": oct_start.isoformat(),
                "end": oct_end.isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(3.0),
                "sum": approx(5.0),
            },
        ]
    }

    dt_util.set_default_time_zone(dt_util.get_time_zone("UTC"))


def _create_engine_test(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    module = "tests.components.recorder.models_schema_23"
    importlib.import_module(module)
    old_models = sys.modules[module]
    engine = create_engine(*args, **kwargs)
    old_models.Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(recorder.models.StatisticsRuns(start=statistics.get_start_time()))
        session.add(
            recorder.models.SchemaChanges(schema_version=old_models.SCHEMA_VERSION)
        )
        session.commit()
    return engine


def test_delete_duplicates(caplog, tmpdir):
    """Test removal of duplicated statistics."""
    test_db_file = tmpdir.mkdir("sqlite").join("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    module = "tests.components.recorder.models_schema_23"
    importlib.import_module(module)
    old_models = sys.modules[module]

    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))

    external_energy_statistics_1 = (
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
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 5,
        },
    )
    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_statistics_2 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 20,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 30,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 40,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 50,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 50,
        },
    )
    external_energy_metadata_2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_2",
        "unit_of_measurement": "kWh",
    }
    external_co2_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "mean": 10,
        },
        {
            "start": period2,
            "last_reset": None,
            "mean": 30,
        },
        {
            "start": period3,
            "last_reset": None,
            "mean": 60,
        },
        {
            "start": period4,
            "last_reset": None,
            "mean": 90,
        },
    )
    external_co2_metadata = {
        "has_mean": True,
        "has_sum": False,
        "name": "Fossil percentage",
        "source": "test",
        "statistic_id": "test:fossil_percentage",
        "unit_of_measurement": "%",
    }

    # Create some duplicated statistics with schema version 23
    with patch.object(recorder, "models", old_models), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_models.SCHEMA_VERSION
    ), patch(
        "homeassistant.components.recorder.create_engine", new=_create_engine_test
    ):
        hass = get_test_home_assistant()
        setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
        wait_recording_done(hass)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            session.add(
                recorder.models.StatisticsMeta.from_meta(external_energy_metadata_1)
            )
            session.add(
                recorder.models.StatisticsMeta.from_meta(external_energy_metadata_2)
            )
            session.add(recorder.models.StatisticsMeta.from_meta(external_co2_metadata))
        with session_scope(hass=hass) as session:
            for stat in external_energy_statistics_1:
                session.add(recorder.models.Statistics.from_stats(1, stat))
            for stat in external_energy_statistics_2:
                session.add(recorder.models.Statistics.from_stats(2, stat))
            for stat in external_co2_statistics:
                session.add(recorder.models.Statistics.from_stats(3, stat))

        hass.stop()
        dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    # Test that the duplicates are removed during migration from schema 23
    hass = get_test_home_assistant()
    setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)
    hass.stop()
    dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    assert "Deleted 2 duplicated statistics rows" in caplog.text
    assert "Found non identical" not in caplog.text
    assert "Found duplicated" not in caplog.text


def test_delete_duplicates_many(caplog, tmpdir):
    """Test removal of duplicated statistics."""
    test_db_file = tmpdir.mkdir("sqlite").join("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    module = "tests.components.recorder.models_schema_23"
    importlib.import_module(module)
    old_models = sys.modules[module]

    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))

    external_energy_statistics_1 = (
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
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 5,
        },
    )
    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_statistics_2 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 20,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 30,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 40,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 50,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 50,
        },
    )
    external_energy_metadata_2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_2",
        "unit_of_measurement": "kWh",
    }
    external_co2_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "mean": 10,
        },
        {
            "start": period2,
            "last_reset": None,
            "mean": 30,
        },
        {
            "start": period3,
            "last_reset": None,
            "mean": 60,
        },
        {
            "start": period4,
            "last_reset": None,
            "mean": 90,
        },
    )
    external_co2_metadata = {
        "has_mean": True,
        "has_sum": False,
        "name": "Fossil percentage",
        "source": "test",
        "statistic_id": "test:fossil_percentage",
        "unit_of_measurement": "%",
    }

    # Create some duplicated statistics with schema version 23
    with patch.object(recorder, "models", old_models), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_models.SCHEMA_VERSION
    ), patch(
        "homeassistant.components.recorder.create_engine", new=_create_engine_test
    ):
        hass = get_test_home_assistant()
        setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
        wait_recording_done(hass)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            session.add(
                recorder.models.StatisticsMeta.from_meta(external_energy_metadata_1)
            )
            session.add(
                recorder.models.StatisticsMeta.from_meta(external_energy_metadata_2)
            )
            session.add(recorder.models.StatisticsMeta.from_meta(external_co2_metadata))
        with session_scope(hass=hass) as session:
            for stat in external_energy_statistics_1:
                session.add(recorder.models.Statistics.from_stats(1, stat))
            for _ in range(3000):
                session.add(
                    recorder.models.Statistics.from_stats(
                        1, external_energy_statistics_1[-1]
                    )
                )
            for stat in external_energy_statistics_2:
                session.add(recorder.models.Statistics.from_stats(2, stat))
            for stat in external_co2_statistics:
                session.add(recorder.models.Statistics.from_stats(3, stat))

        hass.stop()
        dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    # Test that the duplicates are removed during migration from schema 23
    hass = get_test_home_assistant()
    setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)
    hass.stop()
    dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    assert "Deleted 3002 duplicated statistics rows" in caplog.text
    assert "Found non identical" not in caplog.text
    assert "Found duplicated" not in caplog.text


@pytest.mark.freeze_time("2021-08-01 00:00:00+00:00")
def test_delete_duplicates_non_identical(caplog, tmpdir):
    """Test removal of duplicated statistics."""
    test_db_file = tmpdir.mkdir("sqlite").join("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    module = "tests.components.recorder.models_schema_23"
    importlib.import_module(module)
    old_models = sys.modules[module]

    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))

    external_energy_statistics_1 = (
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
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 6,
        },
    )
    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_statistics_2 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 20,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 30,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 40,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 50,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 50,
        },
    )
    external_energy_metadata_2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_2",
        "unit_of_measurement": "kWh",
    }

    # Create some duplicated statistics with schema version 23
    with patch.object(recorder, "models", old_models), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_models.SCHEMA_VERSION
    ), patch(
        "homeassistant.components.recorder.create_engine", new=_create_engine_test
    ):
        hass = get_test_home_assistant()
        setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
        wait_recording_done(hass)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            session.add(
                recorder.models.StatisticsMeta.from_meta(external_energy_metadata_1)
            )
            session.add(
                recorder.models.StatisticsMeta.from_meta(external_energy_metadata_2)
            )
        with session_scope(hass=hass) as session:
            for stat in external_energy_statistics_1:
                session.add(recorder.models.Statistics.from_stats(1, stat))
            for stat in external_energy_statistics_2:
                session.add(recorder.models.Statistics.from_stats(2, stat))

        hass.stop()
        dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    # Test that the duplicates are removed during migration from schema 23
    hass = get_test_home_assistant()
    hass.config.config_dir = tmpdir
    setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)
    hass.stop()
    dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    assert "Deleted 2 duplicated statistics rows" in caplog.text
    assert "Deleted 1 non identical" in caplog.text
    assert "Found duplicated" not in caplog.text

    isotime = dt_util.utcnow().isoformat()
    backup_file_name = f".storage/deleted_statistics.{isotime}.json"

    with open(hass.config.path(backup_file_name)) as backup_file:
        backup = json.load(backup_file)

    assert backup == [
        {
            "duplicate": {
                "created": "2021-08-01T00:00:00",
                "id": 4,
                "last_reset": None,
                "max": None,
                "mean": None,
                "metadata_id": 1,
                "min": None,
                "start": "2021-10-31T23:00:00",
                "state": 3.0,
                "sum": 5.0,
            },
            "original": {
                "created": "2021-08-01T00:00:00",
                "id": 5,
                "last_reset": None,
                "max": None,
                "mean": None,
                "metadata_id": 1,
                "min": None,
                "start": "2021-10-31T23:00:00",
                "state": 3.0,
                "sum": 6.0,
            },
        }
    ]


def test_delete_duplicates_short_term(caplog, tmpdir):
    """Test removal of duplicated statistics."""
    test_db_file = tmpdir.mkdir("sqlite").join("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    module = "tests.components.recorder.models_schema_23"
    importlib.import_module(module)
    old_models = sys.modules[module]

    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))

    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    statistic_row = {
        "start": period4,
        "last_reset": None,
        "state": 3,
        "sum": 5,
    }

    # Create some duplicated statistics with schema version 23
    with patch.object(recorder, "models", old_models), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_models.SCHEMA_VERSION
    ), patch(
        "homeassistant.components.recorder.create_engine", new=_create_engine_test
    ):
        hass = get_test_home_assistant()
        setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
        wait_recording_done(hass)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            session.add(
                recorder.models.StatisticsMeta.from_meta(external_energy_metadata_1)
            )
        with session_scope(hass=hass) as session:
            session.add(
                recorder.models.StatisticsShortTerm.from_stats(1, statistic_row)
            )
            session.add(
                recorder.models.StatisticsShortTerm.from_stats(1, statistic_row)
            )

        hass.stop()
        dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    # Test that the duplicates are removed during migration from schema 23
    hass = get_test_home_assistant()
    hass.config.config_dir = tmpdir
    setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)
    hass.stop()
    dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    assert "duplicated statistics rows" not in caplog.text
    assert "Found non identical" not in caplog.text
    assert "Deleted duplicated short term statistic" in caplog.text


def test_delete_duplicates_no_duplicates(hass_recorder, caplog):
    """Test removal of duplicated statistics."""
    hass = hass_recorder()
    wait_recording_done(hass)
    with session_scope(hass=hass) as session:
        delete_duplicates(hass.data[DATA_INSTANCE], session)
    assert "duplicated statistics rows" not in caplog.text
    assert "Found non identical" not in caplog.text
    assert "Found duplicated" not in caplog.text


def test_duplicate_statistics_handle_integrity_error(hass_recorder, caplog):
    """Test the recorder does not blow up if statistics is duplicated."""
    hass = hass_recorder()
    wait_recording_done(hass)

    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))

    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_statistics_1 = [
        {
            "start": period1,
            "last_reset": None,
            "state": 3,
            "sum": 5,
        },
    ]
    external_energy_statistics_2 = [
        {
            "start": period2,
            "last_reset": None,
            "state": 3,
            "sum": 6,
        }
    ]

    with patch.object(
        statistics, "_statistics_exists", return_value=False
    ), patch.object(
        statistics, "_insert_statistics", wraps=statistics._insert_statistics
    ) as insert_statistics_mock:
        async_add_external_statistics(
            hass, external_energy_metadata_1, external_energy_statistics_1
        )
        async_add_external_statistics(
            hass, external_energy_metadata_1, external_energy_statistics_1
        )
        async_add_external_statistics(
            hass, external_energy_metadata_1, external_energy_statistics_2
        )
        wait_recording_done(hass)
        assert insert_statistics_mock.call_count == 3

    with session_scope(hass=hass) as session:
        tmp = session.query(recorder.models.Statistics).all()
        assert len(tmp) == 2

    assert "Blocked attempt to insert duplicated statistic rows" in caplog.text


def record_states(hass):
    """Record some test states.

    We inject a bunch of state updates temperature sensors.
    """
    mp = "media_player.test"
    sns1 = "sensor.test1"
    sns2 = "sensor.test2"
    sns3 = "sensor.test3"
    sns4 = "sensor.test4"
    sns1_attr = {
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": TEMP_CELSIUS,
    }
    sns2_attr = {
        "device_class": "humidity",
        "state_class": "measurement",
        "unit_of_measurement": "%",
    }
    sns3_attr = {"device_class": "temperature"}
    sns4_attr = {}

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    zero = dt_util.utcnow()
    one = zero + timedelta(seconds=1 * 5)
    two = one + timedelta(seconds=15 * 5)
    three = two + timedelta(seconds=30 * 5)
    four = three + timedelta(seconds=15 * 5)

    states = {mp: [], sns1: [], sns2: [], sns3: [], sns4: []}
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=one):
        states[mp].append(
            set_state(mp, "idle", attributes={"media_title": str(sentinel.mt1)})
        )
        states[mp].append(
            set_state(mp, "YouTube", attributes={"media_title": str(sentinel.mt2)})
        )
        states[sns1].append(set_state(sns1, "10", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "10", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "10", attributes=sns3_attr))
        states[sns4].append(set_state(sns4, "10", attributes=sns4_attr))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=two):
        states[sns1].append(set_state(sns1, "15", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "15", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "15", attributes=sns3_attr))
        states[sns4].append(set_state(sns4, "15", attributes=sns4_attr))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=three):
        states[sns1].append(set_state(sns1, "20", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "20", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "20", attributes=sns3_attr))
        states[sns4].append(set_state(sns4, "20", attributes=sns4_attr))

    return zero, four, states
