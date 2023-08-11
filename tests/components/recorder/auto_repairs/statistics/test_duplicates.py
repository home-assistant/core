"""Test removing statistics duplicates."""
from collections.abc import Callable

# pylint: disable=invalid-name
import importlib
from pathlib import Path
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import statistics
from homeassistant.components.recorder.auto_repairs.statistics.duplicates import (
    delete_statistics_duplicates,
    delete_statistics_meta_duplicates,
)
from homeassistant.components.recorder.const import SQLITE_URL_PREFIX
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from ...common import wait_recording_done

from tests.common import get_test_home_assistant

ORIG_TZ = dt_util.DEFAULT_TIME_ZONE


def test_delete_duplicates_no_duplicates(
    hass_recorder: Callable[..., HomeAssistant], caplog: pytest.LogCaptureFixture
) -> None:
    """Test removal of duplicated statistics."""
    hass = hass_recorder()
    wait_recording_done(hass)
    instance = recorder.get_instance(hass)
    with session_scope(hass=hass) as session:
        delete_statistics_duplicates(instance, hass, session)
    assert "duplicated statistics rows" not in caplog.text
    assert "Found non identical" not in caplog.text
    assert "Found duplicated" not in caplog.text


def test_duplicate_statistics_handle_integrity_error(
    hass_recorder: Callable[..., HomeAssistant], caplog: pytest.LogCaptureFixture
) -> None:
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
        tmp = session.query(recorder.db_schema.Statistics).all()
        assert len(tmp) == 2

    assert "Blocked attempt to insert duplicated statistic rows" in caplog.text


def _create_engine_28(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    module = "tests.components.recorder.db_schema_28"
    importlib.import_module(module)
    old_db_schema = sys.modules[module]
    engine = create_engine(*args, **kwargs)
    old_db_schema.Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            recorder.db_schema.StatisticsRuns(start=statistics.get_start_time())
        )
        session.add(
            recorder.db_schema.SchemaChanges(
                schema_version=old_db_schema.SCHEMA_VERSION
            )
        )
        session.commit()
    return engine


def test_delete_metadata_duplicates(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test removal of duplicated statistics."""
    test_dir = tmp_path.joinpath("sqlite")
    test_dir.mkdir()
    test_db_file = test_dir.joinpath("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    module = "tests.components.recorder.db_schema_28"
    importlib.import_module(module)
    old_db_schema = sys.modules[module]

    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_metadata_2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_co2_metadata = {
        "has_mean": True,
        "has_sum": False,
        "name": "Fossil percentage",
        "source": "test",
        "statistic_id": "test:fossil_percentage",
        "unit_of_measurement": "%",
    }

    # Create some duplicated statistics_meta with schema version 28
    with patch.object(recorder, "db_schema", old_db_schema), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION
    ), patch(
        "homeassistant.components.recorder.core.create_engine", new=_create_engine_28
    ):
        hass = get_test_home_assistant()
        recorder_helper.async_initialize_recorder(hass)
        setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
        wait_recording_done(hass)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_energy_metadata_1)
            )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_energy_metadata_2)
            )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_co2_metadata)
            )

        with session_scope(hass=hass) as session:
            tmp = session.query(recorder.db_schema.StatisticsMeta).all()
            assert len(tmp) == 3
            assert tmp[0].id == 1
            assert tmp[0].statistic_id == "test:total_energy_import_tariff_1"
            assert tmp[1].id == 2
            assert tmp[1].statistic_id == "test:total_energy_import_tariff_1"
            assert tmp[2].id == 3
            assert tmp[2].statistic_id == "test:fossil_percentage"

        hass.stop()
        dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    # Test that the duplicates are removed during migration from schema 28
    hass = get_test_home_assistant()
    recorder_helper.async_initialize_recorder(hass)
    setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)

    assert "Deleted 1 duplicated statistics_meta rows" in caplog.text
    with session_scope(hass=hass) as session:
        tmp = session.query(recorder.db_schema.StatisticsMeta).all()
        assert len(tmp) == 2
        assert tmp[0].id == 2
        assert tmp[0].statistic_id == "test:total_energy_import_tariff_1"
        assert tmp[1].id == 3
        assert tmp[1].statistic_id == "test:fossil_percentage"

    hass.stop()
    dt_util.DEFAULT_TIME_ZONE = ORIG_TZ


def test_delete_metadata_duplicates_many(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test removal of duplicated statistics."""
    test_dir = tmp_path.joinpath("sqlite")
    test_dir.mkdir()
    test_db_file = test_dir.joinpath("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    module = "tests.components.recorder.db_schema_28"
    importlib.import_module(module)
    old_db_schema = sys.modules[module]

    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_metadata_2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_2",
        "unit_of_measurement": "kWh",
    }
    external_co2_metadata = {
        "has_mean": True,
        "has_sum": False,
        "name": "Fossil percentage",
        "source": "test",
        "statistic_id": "test:fossil_percentage",
        "unit_of_measurement": "%",
    }

    # Create some duplicated statistics with schema version 28
    with patch.object(recorder, "db_schema", old_db_schema), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION
    ), patch(
        "homeassistant.components.recorder.core.create_engine", new=_create_engine_28
    ):
        hass = get_test_home_assistant()
        recorder_helper.async_initialize_recorder(hass)
        setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
        wait_recording_done(hass)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_energy_metadata_1)
            )
            for _ in range(1100):
                session.add(
                    recorder.db_schema.StatisticsMeta.from_meta(
                        external_energy_metadata_1
                    )
                )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_energy_metadata_2)
            )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_energy_metadata_2)
            )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_co2_metadata)
            )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_co2_metadata)
            )

        hass.stop()
        dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    # Test that the duplicates are removed during migration from schema 28
    hass = get_test_home_assistant()
    recorder_helper.async_initialize_recorder(hass)
    setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)

    assert "Deleted 1102 duplicated statistics_meta rows" in caplog.text
    with session_scope(hass=hass) as session:
        tmp = session.query(recorder.db_schema.StatisticsMeta).all()
        assert len(tmp) == 3
        assert tmp[0].id == 1101
        assert tmp[0].statistic_id == "test:total_energy_import_tariff_1"
        assert tmp[1].id == 1103
        assert tmp[1].statistic_id == "test:total_energy_import_tariff_2"
        assert tmp[2].id == 1105
        assert tmp[2].statistic_id == "test:fossil_percentage"

    hass.stop()
    dt_util.DEFAULT_TIME_ZONE = ORIG_TZ


def test_delete_metadata_duplicates_no_duplicates(
    hass_recorder: Callable[..., HomeAssistant], caplog: pytest.LogCaptureFixture
) -> None:
    """Test removal of duplicated statistics."""
    hass = hass_recorder()
    wait_recording_done(hass)
    with session_scope(hass=hass) as session:
        instance = recorder.get_instance(hass)
        delete_statistics_meta_duplicates(instance, session)
    assert "duplicated statistics_meta rows" not in caplog.text
