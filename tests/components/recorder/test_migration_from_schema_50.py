"""The tests for the recorder filter matching the EntityFilter component."""

import importlib
import sys
import threading
from unittest.mock import patch

import pytest
from pytest_unordered import unordered
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import core, migration, statistics
from homeassistant.components.recorder.const import UNIT_CLASS_SCHEMA_VERSION
from homeassistant.components.recorder.db_schema import StatisticsMeta
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant

from .common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
    get_patched_live_version,
)
from .conftest import instrument_migration

from tests.common import async_test_home_assistant
from tests.typing import RecorderInstanceContextManager

CREATE_ENGINE_TARGET = "homeassistant.components.recorder.core.create_engine"
SCHEMA_MODULE_50 = "tests.components.recorder.db_schema_50"


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


async def _async_wait_migration_done(hass: HomeAssistant) -> None:
    """Wait for the migration to be done."""
    await recorder.get_instance(hass).async_block_till_done()
    await async_recorder_block_till_done(hass)


def _create_engine_test(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    importlib.import_module(SCHEMA_MODULE_50)
    old_db_schema = sys.modules[SCHEMA_MODULE_50]
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


@pytest.fixture
def db_schema_50():
    """Fixture to initialize the db with the old schema."""
    importlib.import_module(SCHEMA_MODULE_50)
    old_db_schema = sys.modules[SCHEMA_MODULE_50]

    with (
        patch.object(recorder, "db_schema", old_db_schema),
        patch.object(migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION),
        patch.object(
            migration,
            "LIVE_MIGRATION_MIN_SCHEMA_VERSION",
            get_patched_live_version(old_db_schema),
        ),
        patch.object(migration, "non_live_data_migration_needed", return_value=False),
        patch.object(core, "StatesMeta", old_db_schema.StatesMeta),
        patch.object(core, "EventTypes", old_db_schema.EventTypes),
        patch.object(core, "EventData", old_db_schema.EventData),
        patch.object(core, "States", old_db_schema.States),
        patch.object(core, "Events", old_db_schema.Events),
        patch.object(core, "StateAttributes", old_db_schema.StateAttributes),
        patch(CREATE_ENGINE_TARGET, new=_create_engine_test),
    ):
        yield


@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.usefixtures("hass_storage")  # Prevent test hass from writing to storage
async def test_migrate_statistics_meta(
    async_test_recorder: RecorderInstanceContextManager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test migration of metadata adding unit_class."""
    importlib.import_module(SCHEMA_MODULE_50)
    old_db_schema = sys.modules[SCHEMA_MODULE_50]

    def _insert_metadata():
        with session_scope(hass=hass) as session:
            session.add_all(
                (
                    old_db_schema.StatisticsMeta(
                        statistic_id="sensor.test1",
                        source="recorder",
                        unit_of_measurement="kWh",
                        has_mean=None,
                        has_sum=True,
                        name="Test 1",
                        mean_type=StatisticMeanType.NONE,
                    ),
                    old_db_schema.StatisticsMeta(
                        statistic_id="sensor.test2",
                        source="recorder",
                        unit_of_measurement="cats",
                        has_mean=None,
                        has_sum=True,
                        name="Test 2",
                        mean_type=StatisticMeanType.NONE,
                    ),
                    old_db_schema.StatisticsMeta(
                        statistic_id="sensor.test3",
                        source="recorder",
                        unit_of_measurement="ppm",
                        has_mean=None,
                        has_sum=True,
                        name="Test 3",
                        mean_type=StatisticMeanType.NONE,
                    ),
                )
            )

    # Create database with old schema
    with (
        patch.object(recorder, "db_schema", old_db_schema),
        patch.object(migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION),
        patch.object(
            migration,
            "LIVE_MIGRATION_MIN_SCHEMA_VERSION",
            get_patched_live_version(old_db_schema),
        ),
        patch.object(migration.EventsContextIDMigration, "migrate_data"),
        patch(CREATE_ENGINE_TARGET, new=_create_engine_test),
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass) as instance,
        ):
            await instance.async_add_executor_job(_insert_metadata)

            await async_wait_recording_done(hass)
            await _async_wait_migration_done(hass)

            await hass.async_stop()
            await hass.async_block_till_done()

    def _object_as_dict(obj):
        return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}

    def _fetch_metadata():
        with session_scope(hass=hass) as session:
            metadatas = session.query(StatisticsMeta).all()
            return {
                metadata.statistic_id: _object_as_dict(metadata)
                for metadata in metadatas
            }

    # Run again with new schema, let migration run
    async with async_test_home_assistant() as hass:
        with (
            instrument_migration(hass) as instrumented_migration,
        ):
            # Stall migration when the last non-live schema migration is done
            instrumented_migration.stall_on_schema_version = UNIT_CLASS_SCHEMA_VERSION
            async with async_test_recorder(
                hass, wait_recorder=False, wait_recorder_setup=False
            ) as instance:
                # Wait for migration to reach migration of unit class
                await hass.async_add_executor_job(
                    instrumented_migration.apply_update_stalled.wait
                )

                # Check that it's possible to read metadata via the API, this will
                # stop working when version 50 is migrated off line
                pre_migration_metadata_api = await instance.async_add_executor_job(
                    statistics.list_statistic_ids,
                    hass,
                    None,
                    None,
                )

                instrumented_migration.migration_stall.set()
                instance.recorder_and_worker_thread_ids.add(threading.get_ident())

                await hass.async_block_till_done()
                await async_wait_recording_done(hass)
                await async_wait_recording_done(hass)

                post_migration_metadata_db = await instance.async_add_executor_job(
                    _fetch_metadata
                )
                post_migration_metadata_api = await instance.async_add_executor_job(
                    statistics.list_statistic_ids,
                    hass,
                    None,
                    None,
                )

                await hass.async_stop()
                await hass.async_block_till_done()

    assert pre_migration_metadata_api == unordered(
        [
            {
                "display_unit_of_measurement": "kWh",
                "has_mean": False,
                "has_sum": True,
                "mean_type": StatisticMeanType.NONE,
                "name": "Test 1",
                "source": "recorder",
                "statistic_id": "sensor.test1",
                "statistics_unit_of_measurement": "kWh",
                "unit_class": "energy",
            },
            {
                "display_unit_of_measurement": "cats",
                "has_mean": False,
                "has_sum": True,
                "mean_type": StatisticMeanType.NONE,
                "name": "Test 2",
                "source": "recorder",
                "statistic_id": "sensor.test2",
                "statistics_unit_of_measurement": "cats",
                "unit_class": None,
            },
            {
                "display_unit_of_measurement": "ppm",
                "has_mean": False,
                "has_sum": True,
                "mean_type": StatisticMeanType.NONE,
                "name": "Test 3",
                "source": "recorder",
                "statistic_id": "sensor.test3",
                "statistics_unit_of_measurement": "ppm",
                "unit_class": "unitless",
            },
        ]
    )
    assert post_migration_metadata_db == {
        "sensor.test1": {
            "has_mean": None,
            "has_sum": True,
            "id": 1,
            "mean_type": 0,
            "name": "Test 1",
            "source": "recorder",
            "statistic_id": "sensor.test1",
            "unit_class": "energy",
            "unit_of_measurement": "kWh",
        },
        "sensor.test2": {
            "has_mean": None,
            "has_sum": True,
            "id": 2,
            "mean_type": 0,
            "name": "Test 2",
            "source": "recorder",
            "statistic_id": "sensor.test2",
            "unit_class": None,
            "unit_of_measurement": "cats",
        },
        "sensor.test3": {
            "has_mean": None,
            "has_sum": True,
            "id": 3,
            "mean_type": 0,
            "name": "Test 3",
            "source": "recorder",
            "statistic_id": "sensor.test3",
            "unit_class": "unitless",
            "unit_of_measurement": "ppm",
        },
    }
    assert post_migration_metadata_api == unordered(pre_migration_metadata_api)
