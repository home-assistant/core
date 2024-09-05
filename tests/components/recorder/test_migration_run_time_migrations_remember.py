"""Test run time migrations are remembered in the migration_changes table."""

import importlib
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import core, migration, statistics
from homeassistant.components.recorder.migration import MigrationTask
from homeassistant.components.recorder.queries import get_migration_changes
from homeassistant.components.recorder.util import (
    execute_stmt_lambda_element,
    session_scope,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .common import (
    MockMigrationTask,
    async_recorder_block_till_done,
    async_wait_recording_done,
)

from tests.common import async_test_home_assistant
from tests.typing import RecorderInstanceGenerator

CREATE_ENGINE_TARGET = "homeassistant.components.recorder.core.create_engine"
SCHEMA_MODULE = "tests.components.recorder.db_schema_32"


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceGenerator,
) -> None:
    """Set up recorder."""


async def _async_wait_migration_done(hass: HomeAssistant) -> None:
    """Wait for the migration to be done."""
    await recorder.get_instance(hass).async_block_till_done()
    await async_recorder_block_till_done(hass)


def _get_migration_id(hass: HomeAssistant) -> dict[str, int]:
    with session_scope(hass=hass, read_only=True) as session:
        return dict(execute_stmt_lambda_element(session, get_migration_changes()))


def _create_engine_test(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    importlib.import_module(SCHEMA_MODULE)
    old_db_schema = sys.modules[SCHEMA_MODULE]
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


@pytest.mark.parametrize("enable_migrate_state_context_ids", [True])
@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.usefixtures("hass_storage")  # Prevent test hass from writing to storage
async def test_migration_changes_prevent_trying_to_migrate_again(
    async_test_recorder: RecorderInstanceGenerator,
) -> None:
    """Test that we do not try to migrate when migration_changes indicate its already migrated.

    This test will start Home Assistant 3 times:

    1. With schema 32 to populate the data
    2. With current schema so the migration happens
    3. With current schema to verify we do not have to query to see if the migration is done
    """

    config = {recorder.CONF_COMMIT_INTERVAL: 1}
    importlib.import_module(SCHEMA_MODULE)
    old_db_schema = sys.modules[SCHEMA_MODULE]

    # Start with db schema that needs migration (version 32)
    with (
        patch.object(recorder, "db_schema", old_db_schema),
        patch.object(
            recorder.migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION
        ),
        patch.object(core, "StatesMeta", old_db_schema.StatesMeta),
        patch.object(core, "EventTypes", old_db_schema.EventTypes),
        patch.object(core, "EventData", old_db_schema.EventData),
        patch.object(core, "States", old_db_schema.States),
        patch.object(core, "Events", old_db_schema.Events),
        patch.object(core, "StateAttributes", old_db_schema.StateAttributes),
        patch.object(migration.EntityIDMigration, "task", MockMigrationTask),
        patch(CREATE_ENGINE_TARGET, new=_create_engine_test),
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass, config),
        ):
            await hass.async_block_till_done()
            await async_wait_recording_done(hass)
            await _async_wait_migration_done(hass)
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()
            await hass.async_stop()

    # Now start again with current db schema
    async with async_test_home_assistant() as hass, async_test_recorder(hass, config):
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
        await _async_wait_migration_done(hass)
        instance = recorder.get_instance(hass)
        migration_changes = await instance.async_add_executor_job(
            _get_migration_id, hass
        )
        assert (
            migration_changes[migration.StatesContextIDMigration.migration_id]
            == migration.StatesContextIDMigration.migration_version
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        await hass.async_stop()

    original_queue_task = core.Recorder.queue_task
    tasks = []

    def _queue_task(self, task):
        tasks.append(task)
        original_queue_task(self, task)

    # Finally verify we did not call needs_migrate_query on StatesContextIDMigration
    with (
        patch(
            "homeassistant.components.recorder.core.Recorder.queue_task",
            _queue_task,
        ),
        patch.object(
            migration.StatesContextIDMigration,
            "needs_migrate_query",
            side_effect=RuntimeError("Should not be called"),
        ),
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass, config),
        ):
            await hass.async_block_till_done()
            await async_wait_recording_done(hass)
            await _async_wait_migration_done(hass)
            instance = recorder.get_instance(hass)
            migration_changes = await instance.async_add_executor_job(
                _get_migration_id, hass
            )
            assert (
                migration_changes[migration.StatesContextIDMigration.migration_id]
                == migration.StatesContextIDMigration.migration_version
            )
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()
            await hass.async_stop()

    for task in tasks:
        assert not isinstance(task, MigrationTask)
